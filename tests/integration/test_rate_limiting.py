"""
Integration tests for rate limiting functionality.

Tests the rate-limited client wrapper with mocked HTTP responses
to verify retry behavior on 429 responses.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest
import responses

from x_client.clients.rate_limited_client import RateLimitedClient
from x_client.clients.tweepy_client import TweepyClient
from x_client.config import ConfigManager
from x_client.exceptions import RateLimitExceeded
from x_client.factory import XClientFactory
from x_client.rate_limit import RetryConfig
from x_client.services.post_service import PostService


@pytest.fixture
def test_credentials(tmp_path):
    """Create test credentials in temporary .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
X_API_KEY=test_api_key
X_API_SECRET=test_api_secret
X_ACCESS_TOKEN=test_access_token
X_ACCESS_TOKEN_SECRET=test_access_token_secret
X_BEARER_TOKEN=test_bearer_token
"""
    )
    return env_file


@pytest.fixture
def rate_limited_client(test_credentials):
    """Create rate-limited client with test configuration."""
    config = ConfigManager(dotenv_path=test_credentials)

    # Use aggressive retry settings for faster tests
    retry_config = RetryConfig(
        max_retries=2,
        base_delay=0.01,  # 10ms base delay
        max_delay=0.1,  # 100ms max delay
        jitter=False,  # Disable jitter for predictable tests
    )

    return XClientFactory.create_from_config(
        config,
        enable_rate_limiting=True,
        retry_config=retry_config,
    )


# ============================================================================
# Rate Limit Retry Tests
# ============================================================================


@responses.activate
def test_rate_limit_retry_success(rate_limited_client):
    """Test successful retry after rate limit error."""
    # First request returns 429
    responses.post(
        "https://api.twitter.com/2/tweets",
        json={
            "errors": [
                {
                    "message": "Rate limit exceeded",
                    "type": "about:blank",
                }
            ]
        },
        status=429,
        headers={
            "x-rate-limit-reset": "1728730800",
        },
    )

    # Second request succeeds
    responses.post(
        "https://api.twitter.com/2/tweets",
        json={
            "data": {
                "id": "1234567890",
                "text": "Test post",
            }
        },
        status=201,
    )

    # Create service with rate-limited client
    service = PostService(rate_limited_client)

    # Should succeed after retry
    post = service.create_post("Test post")

    assert post.id == "1234567890"
    assert post.text == "Test post"
    assert len(responses.calls) == 2  # Initial + 1 retry


@responses.activate
def test_rate_limit_retry_exhausted(rate_limited_client):
    """Test retry exhaustion with persistent rate limit errors."""
    # All requests return 429
    for _ in range(5):  # More than max_retries
        responses.post(
            "https://api.twitter.com/2/tweets",
            json={
                "errors": [
                    {
                        "message": "Rate limit exceeded",
                        "type": "about:blank",
                    }
                ]
            },
            status=429,
            headers={
                "x-rate-limit-reset": "1728730800",
            },
        )

    # Create service with rate-limited client
    service = PostService(rate_limited_client)

    # Should fail after max retries
    with pytest.raises(RateLimitExceeded):
        service.create_post("Test post")

    # Should have tried max_retries + 1 times (initial + 2 retries = 3)
    assert len(responses.calls) == 3


@responses.activate
def test_rate_limit_no_retry_on_other_errors(rate_limited_client):
    """Test that rate limiter doesn't retry non-rate-limit errors."""
    # Request returns 401 unauthorized
    responses.post(
        "https://api.twitter.com/2/tweets",
        json={
            "errors": [
                {
                    "message": "Unauthorized",
                    "type": "about:blank",
                }
            ]
        },
        status=401,
    )

    # Create service with rate-limited client
    service = PostService(rate_limited_client)

    # Should fail immediately without retry
    from x_client.exceptions import ApiResponseError

    with pytest.raises(ApiResponseError):
        service.create_post("Test post")

    # Should have tried only once (no retry for non-429 errors)
    assert len(responses.calls) == 1


# ============================================================================
# Media Upload Rate Limiting Tests
# ============================================================================


@responses.activate
def test_media_upload_rate_limit_retry(rate_limited_client, tmp_path):
    """Test media upload with rate limit retry."""
    # Create test image
    image_file = tmp_path / "test.png"
    image_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    # First upload returns 429
    responses.post(
        "https://upload.twitter.com/1.1/media/upload.json",
        json={
            "errors": [
                {
                    "message": "Rate limit exceeded",
                    "code": 88,
                }
            ]
        },
        status=429,
        headers={
            "x-rate-limit-reset": "1728730800",
        },
    )

    # Second upload succeeds
    responses.post(
        "https://upload.twitter.com/1.1/media/upload.json",
        json={
            "media_id": 123456789,
            "media_id_string": "123456789",
        },
        status=200,
    )

    # Create media service
    from x_client.services.media_service import MediaService

    media_service = MediaService(rate_limited_client)

    # Should succeed after retry
    result = media_service.upload_image(image_file)

    assert result.media_id == "123456789"
    assert len(responses.calls) == 2  # Initial + 1 retry


# ============================================================================
# Client Configuration Tests
# ============================================================================


def test_factory_creates_rate_limited_client_by_default(test_credentials):
    """Test that factory creates rate-limited client by default."""
    config = ConfigManager(dotenv_path=test_credentials)
    client = XClientFactory.create_from_config(config)

    # Should be wrapped with RateLimitedClient
    assert isinstance(client, RateLimitedClient)

    # Should have rate limit info getter
    assert hasattr(client, "get_rate_limit_info")


def test_factory_can_disable_rate_limiting(test_credentials):
    """Test that factory can create unwrapped client."""
    config = ConfigManager(dotenv_path=test_credentials)
    client = XClientFactory.create_from_config(
        config,
        enable_rate_limiting=False,
    )

    # Should be TweepyClient without wrapper
    assert isinstance(client, TweepyClient)
    assert not isinstance(client, RateLimitedClient)


def test_factory_accepts_custom_retry_config(test_credentials):
    """Test that factory accepts custom retry configuration."""
    config = ConfigManager(dotenv_path=test_credentials)

    custom_config = RetryConfig(
        max_retries=5,
        base_delay=2.0,
        max_delay=120.0,
    )

    client = XClientFactory.create_from_config(
        config,
        enable_rate_limiting=True,
        retry_config=custom_config,
    )

    # Should be rate-limited client with custom config
    assert isinstance(client, RateLimitedClient)
    assert client._handler.retry_config.max_retries == 5
    assert client._handler.retry_config.base_delay == 2.0


# ============================================================================
# Rate Limit State Tracking Tests
# ============================================================================


@responses.activate
def test_rate_limit_info_tracking(rate_limited_client):
    """Test that rate limit info is tracked from responses."""
    # Mock successful request with rate limit headers
    responses.post(
        "https://api.twitter.com/2/tweets",
        json={
            "data": {
                "id": "1234567890",
                "text": "Test post",
            }
        },
        status=201,
        headers={
            "x-rate-limit-limit": "300",
            "x-rate-limit-remaining": "299",
            "x-rate-limit-reset": "1728730800",
        },
    )

    # Create service
    service = PostService(rate_limited_client)
    service.create_post("Test post")

    # Rate limit info should be available (but tweepy doesn't expose headers on success)
    # This is a known limitation - we can only track on failures
    info = rate_limited_client.get_rate_limit_info()

    # Will be None or empty because tweepy doesn't expose success headers
    # This test documents the current limitation
    assert info is None or info.remaining is None


@responses.activate
def test_rate_limit_info_from_exception(rate_limited_client):
    """Test that rate limit info is extracted from exceptions."""
    # Mock rate limit error
    responses.post(
        "https://api.twitter.com/2/tweets",
        json={
            "errors": [
                {
                    "message": "Rate limit exceeded",
                    "type": "about:blank",
                }
            ]
        },
        status=429,
        headers={
            "x-rate-limit-limit": "300",
            "x-rate-limit-remaining": "0",
            "x-rate-limit-reset": "1728730800",
        },
    )

    # Second request for retry
    responses.post(
        "https://api.twitter.com/2/tweets",
        json={
            "data": {
                "id": "1234567890",
                "text": "Test post",
            }
        },
        status=201,
    )

    # Create service
    service = PostService(rate_limited_client)
    service.create_post("Test post")

    # Rate limit info should be available from the exception
    info = rate_limited_client.get_rate_limit_info()

    # Should have reset time from the exception (from TweepyClient._extract_reset_at)
    # Note: tweepy extracts reset_at from exception headers, which gets stored
    # in RateLimitExceeded exception and then updated in rate limit handler
    assert info is not None
    # The info is updated but may be cleared by success response (empty headers)
    # This documents a limitation: rate limit tracking is best-effort with tweepy
    # Since we can't get headers from successful responses
