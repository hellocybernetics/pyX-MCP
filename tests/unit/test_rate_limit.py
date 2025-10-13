"""
Unit tests for rate limiting and retry logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from x_client.exceptions import RateLimitExceeded
from x_client.rate_limit import (
    RateLimitHandler,
    RateLimitInfo,
    RetryConfig,
)


# ============================================================================
# RateLimitInfo Tests
# ============================================================================


def test_rate_limit_info_from_headers():
    """Test parsing rate limit info from Twitter API headers."""
    headers = {
        "x-rate-limit-limit": "300",
        "x-rate-limit-remaining": "299",
        "x-rate-limit-reset": "1728730800",
    }

    info = RateLimitInfo.from_headers(headers)

    assert info.limit == 300
    assert info.remaining == 299
    assert info.reset_at == 1728730800


def test_rate_limit_info_from_headers_case_insensitive():
    """Test header parsing is case-insensitive."""
    headers = {
        "X-Rate-Limit-Limit": "300",
        "X-RATE-LIMIT-REMAINING": "299",
        "x-RATE-limit-RESET": "1728730800",
    }

    info = RateLimitInfo.from_headers(headers)

    assert info.limit == 300
    assert info.remaining == 299
    assert info.reset_at == 1728730800


def test_rate_limit_info_from_headers_missing_values():
    """Test handling missing rate limit headers."""
    headers = {}

    info = RateLimitInfo.from_headers(headers)

    assert info.limit is None
    assert info.remaining is None
    assert info.reset_at is None


def test_rate_limit_info_is_exhausted():
    """Test rate limit exhaustion detection."""
    # Not exhausted
    info = RateLimitInfo(limit=300, remaining=10, reset_at=1728730800)
    assert not info.is_exhausted()

    # Exhausted
    info = RateLimitInfo(limit=300, remaining=0, reset_at=1728730800)
    assert info.is_exhausted()

    # Unknown state (no remaining count)
    info = RateLimitInfo(limit=300, remaining=None, reset_at=1728730800)
    assert not info.is_exhausted()


def test_rate_limit_info_seconds_until_reset():
    """Test calculating seconds until rate limit reset."""
    # Future reset time
    now = datetime.now(timezone.utc).timestamp()
    future_reset = int(now + 3600)  # 1 hour from now

    info = RateLimitInfo(limit=300, remaining=0, reset_at=future_reset)
    seconds = info.seconds_until_reset()

    assert seconds is not None
    assert 3550 <= seconds <= 3610  # Allow some tolerance for test execution time

    # Past reset time (should return 0)
    past_reset = int(now - 3600)  # 1 hour ago
    info = RateLimitInfo(limit=300, remaining=0, reset_at=past_reset)
    assert info.seconds_until_reset() == 0.0

    # No reset time
    info = RateLimitInfo(limit=300, remaining=0, reset_at=None)
    assert info.seconds_until_reset() is None


# ============================================================================
# RetryConfig Tests
# ============================================================================


def test_retry_config_calculate_delay_exponential():
    """Test exponential backoff calculation without jitter."""
    config = RetryConfig(
        base_delay=1.0,
        exponential_base=2.0,
        max_delay=60.0,
        jitter=False,
    )

    # Attempt 0: 1.0 * 2^0 = 1.0
    assert config.calculate_delay(0) == 1.0

    # Attempt 1: 1.0 * 2^1 = 2.0
    assert config.calculate_delay(1) == 2.0

    # Attempt 2: 1.0 * 2^2 = 4.0
    assert config.calculate_delay(2) == 4.0

    # Attempt 3: 1.0 * 2^3 = 8.0
    assert config.calculate_delay(3) == 8.0


def test_retry_config_calculate_delay_max_cap():
    """Test delay is capped at max_delay."""
    config = RetryConfig(
        base_delay=1.0,
        exponential_base=2.0,
        max_delay=10.0,
        jitter=False,
    )

    # Attempt 10: 1.0 * 2^10 = 1024.0, but capped at 10.0
    assert config.calculate_delay(10) == 10.0


def test_retry_config_calculate_delay_with_jitter():
    """Test jitter adds randomization to delay."""
    config = RetryConfig(
        base_delay=1.0,
        exponential_base=2.0,
        max_delay=60.0,
        jitter=True,
    )

    # With jitter, delay should be random between 0 and calculated value
    delays = [config.calculate_delay(2) for _ in range(100)]

    # All delays should be between 0 and 4.0 (calculated delay for attempt 2)
    assert all(0.0 <= d <= 4.0 for d in delays)

    # Should have some variance (not all the same)
    assert len(set(delays)) > 10  # Expect multiple different values


# ============================================================================
# RateLimitHandler Tests
# ============================================================================


def test_rate_limit_handler_update_and_get():
    """Test updating and retrieving rate limit info."""
    handler = RateLimitHandler()

    # Initially no rate limit info
    assert handler.get_rate_limit_info() is None

    # Update with headers
    headers = {
        "x-rate-limit-limit": "300",
        "x-rate-limit-remaining": "299",
        "x-rate-limit-reset": "1728730800",
    }
    handler.update_rate_limit(headers)

    # Should now have rate limit info
    info = handler.get_rate_limit_info()
    assert info is not None
    assert info.limit == 300
    assert info.remaining == 299


def test_rate_limit_handler_wait_if_needed_not_exhausted():
    """Test wait_if_needed does nothing when rate limit not exhausted."""
    handler = RateLimitHandler()
    mock_sleep = Mock()
    handler.sleep = mock_sleep

    # Set rate limit with remaining requests
    headers = {
        "x-rate-limit-limit": "300",
        "x-rate-limit-remaining": "10",
        "x-rate-limit-reset": "1728730800",
    }
    handler.update_rate_limit(headers)

    # Should not wait
    handler.wait_if_needed()
    mock_sleep.assert_not_called()


def test_rate_limit_handler_wait_if_needed_exhausted():
    """Test wait_if_needed waits when rate limit exhausted."""
    handler = RateLimitHandler()
    mock_sleep = Mock()
    handler.sleep = mock_sleep

    # Set exhausted rate limit with future reset
    now = datetime.now(timezone.utc).timestamp()
    future_reset = int(now + 10)  # 10 seconds from now

    headers = {
        "x-rate-limit-limit": "300",
        "x-rate-limit-remaining": "0",
        "x-rate-limit-reset": str(future_reset),
    }
    handler.update_rate_limit(headers)

    # Should wait
    handler.wait_if_needed()
    mock_sleep.assert_called_once()

    # Should wait approximately 10 seconds
    wait_time = mock_sleep.call_args[0][0]
    assert 9.0 <= wait_time <= 11.0


def test_rate_limit_handler_wait_if_needed_no_reset_time():
    """Test wait_if_needed raises if exhausted with no reset time."""
    handler = RateLimitHandler()

    # Set exhausted rate limit without reset time
    headers = {
        "x-rate-limit-limit": "300",
        "x-rate-limit-remaining": "0",
    }
    handler.update_rate_limit(headers)

    # Should raise exception
    with pytest.raises(RateLimitExceeded) as exc_info:
        handler.wait_if_needed()

    assert "unknown reset time" in str(exc_info.value).lower()


def test_rate_limit_handler_execute_with_retry_success():
    """Test execute_with_retry with successful operation."""
    handler = RateLimitHandler()

    # Mock operation that succeeds
    mock_operation = Mock(
        return_value=(
            "success",
            {"x-rate-limit-remaining": "299"},
        )
    )

    result = handler.execute_with_retry(mock_operation)

    assert result == "success"
    mock_operation.assert_called_once()


def test_rate_limit_handler_execute_with_retry_rate_limit():
    """Test execute_with_retry handles rate limit with retry."""
    config = RetryConfig(max_retries=2, base_delay=0.1, jitter=False)
    handler = RateLimitHandler(retry_config=config)
    mock_sleep = Mock()
    handler.sleep = mock_sleep

    # Mock operation that fails with rate limit, then succeeds
    now = datetime.now(timezone.utc).timestamp()
    future_reset = int(now + 1)

    mock_operation = Mock(
        side_effect=[
            RateLimitExceeded("Rate limit", reset_at=future_reset),
            ("success", {"x-rate-limit-remaining": "299"}),
        ]
    )

    result = handler.execute_with_retry(mock_operation)

    assert result == "success"
    assert mock_operation.call_count == 2

    # Should have applied exponential backoff (not full reset wait)
    assert mock_sleep.call_count == 1
    wait_time = mock_sleep.call_args[0][0]
    assert wait_time == pytest.approx(config.calculate_delay(0))


def test_rate_limit_handler_clears_cached_limit_after_wait():
    """Ensure cached rate limit is cleared so subsequent calls don't stall."""
    config = RetryConfig(max_retries=1, base_delay=0.1, jitter=False)
    handler = RateLimitHandler(retry_config=config)
    mock_sleep = Mock()
    handler.sleep = mock_sleep

    now = datetime.now(timezone.utc).timestamp()
    future_reset = int(now + 1)

    mock_operation = Mock(
        side_effect=[
            RateLimitExceeded("Rate limit", reset_at=future_reset),
            ("success", {}),  # empty headers mimic tweepy v2 behaviour
        ]
    )

    result = handler.execute_with_retry(mock_operation)

    assert result == "success"
    assert mock_operation.call_count == 2
    assert mock_sleep.call_count == 1

    info = handler.get_rate_limit_info()
    assert info is None or not info.is_exhausted()


def test_rate_limit_handler_execute_with_retry_max_retries():
    """Test execute_with_retry respects max retries."""
    config = RetryConfig(max_retries=2, base_delay=0.01, jitter=False)
    handler = RateLimitHandler(retry_config=config)
    mock_sleep = Mock()
    handler.sleep = mock_sleep

    # Mock operation that always fails
    now = datetime.now(timezone.utc).timestamp()
    future_reset = int(now + 1)

    mock_operation = Mock(
        side_effect=RateLimitExceeded("Rate limit", reset_at=future_reset)
    )

    # Should fail after max retries
    with pytest.raises(RateLimitExceeded):
        handler.execute_with_retry(mock_operation)

    # Should have tried max_retries + 1 times (initial + 2 retries)
    assert mock_operation.call_count == 3


def test_rate_limit_handler_execute_with_retry_non_retryable():
    """Test execute_with_retry does not retry non-retryable exceptions."""
    handler = RateLimitHandler()

    # Mock operation that fails with non-retryable exception
    mock_operation = Mock(side_effect=ValueError("Invalid value"))

    # Should fail immediately without retry
    with pytest.raises(ValueError):
        handler.execute_with_retry(mock_operation)

    mock_operation.assert_called_once()


def test_rate_limit_handler_execute_with_retry_custom_predicate():
    """Test execute_with_retry with custom retry predicate."""
    config = RetryConfig(max_retries=2, base_delay=0.01, jitter=False)
    handler = RateLimitHandler(retry_config=config)
    mock_sleep = Mock()
    handler.sleep = mock_sleep

    # Mock operation that fails with ValueError
    mock_operation = Mock(
        side_effect=[
            ValueError("Transient error"),
            ("success", {"x-rate-limit-remaining": "299"}),
        ]
    )

    # Custom predicate that treats ValueError as retryable
    def should_retry(e):
        return isinstance(e, (RateLimitExceeded, ValueError))

    result = handler.execute_with_retry(mock_operation, should_retry=should_retry)

    assert result == "success"
    assert mock_operation.call_count == 2
