"""
Rate limiting and retry logic for X API.

Implements exponential backoff with jitter for handling rate limits
and transient failures gracefully.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from x_client.exceptions import RateLimitExceeded

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RateLimitInfo:
    """Rate limit information from API response headers."""

    limit: int | None = None  # Total request limit
    remaining: int | None = None  # Remaining requests
    reset_at: int | None = None  # Unix timestamp when limit resets

    @classmethod
    def from_headers(cls, headers: dict[str, str]) -> RateLimitInfo:
        """
        Extract rate limit info from X API response headers.

        Args:
            headers: Response headers dict (case-insensitive keys)

        Returns:
            RateLimitInfo with extracted values
        """
        # X uses x-rate-limit-* headers
        headers_lower = {k.lower(): v for k, v in headers.items()}

        limit = headers_lower.get("x-rate-limit-limit")
        remaining = headers_lower.get("x-rate-limit-remaining")
        reset = headers_lower.get("x-rate-limit-reset")

        return cls(
            limit=int(limit) if limit else None,
            remaining=int(remaining) if remaining else None,
            reset_at=int(reset) if reset else None,
        )

    def is_exhausted(self) -> bool:
        """Check if rate limit is exhausted."""
        return self.remaining is not None and self.remaining <= 0

    def seconds_until_reset(self) -> float | None:
        """Calculate seconds until rate limit resets."""
        if self.reset_at is None:
            return None
        now = datetime.now(timezone.utc).timestamp()
        return max(0.0, self.reset_at - now)


@dataclass(slots=True)
class RetryConfig:
    """Configuration for retry behavior with exponential backoff."""

    max_retries: int = 3
    base_delay: float = 1.0  # Initial delay in seconds
    max_delay: float = 60.0  # Maximum delay cap
    exponential_base: float = 2.0  # Multiplier for exponential backoff
    jitter: bool = True  # Add randomization to prevent thundering herd

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for given retry attempt using exponential backoff.

        Args:
            attempt: Retry attempt number (0-indexed)

        Returns:
            Delay in seconds with optional jitter
        """
        # Exponential backoff: base_delay * (exponential_base ^ attempt)
        delay = min(self.base_delay * (self.exponential_base**attempt), self.max_delay)

        # Add jitter: random value between 0 and delay
        if self.jitter:
            delay = random.uniform(0, delay)

        return delay


@dataclass(slots=True)
class RateLimitHandler:
    """
    Handle rate limiting with automatic retry and exponential backoff.

    Tracks rate limit state and implements retry logic for API calls.
    """

    retry_config: RetryConfig = field(default_factory=RetryConfig)
    sleep: Callable[[float], None] = field(default=time.sleep)
    _last_rate_limit: RateLimitInfo | None = field(default=None, init=False)

    def update_rate_limit(self, headers: dict[str, str]) -> None:
        """
        Update rate limit info from API response headers.

        Args:
            headers: Response headers from API call
        """
        self._last_rate_limit = RateLimitInfo.from_headers(headers)

        if self._last_rate_limit.remaining is not None:
            logger.debug(
                f"Rate limit: {self._last_rate_limit.remaining}/{self._last_rate_limit.limit} remaining"
            )

    def get_rate_limit_info(self) -> RateLimitInfo | None:
        """Get current rate limit information."""
        return self._last_rate_limit

    def wait_if_needed(self) -> None:
        """
        Wait if rate limit is exhausted.

        Raises:
            RateLimitExceeded: If rate limit exhausted and reset time unknown
        """
        if self._last_rate_limit is None or not self._last_rate_limit.is_exhausted():
            return

        wait_time = self._last_rate_limit.seconds_until_reset()
        if wait_time is None:
            raise RateLimitExceeded(
                "Rate limit exhausted with unknown reset time",
                reset_at=self._last_rate_limit.reset_at,
            )

        if wait_time > 0:
            logger.warning(f"Rate limit exhausted. Waiting {wait_time:.1f}s until reset...")
            self.sleep(wait_time)

    def execute_with_retry(
        self,
        operation: Callable[[], tuple[any, dict[str, str]]],
        should_retry: Callable[[Exception], bool] | None = None,
    ) -> any:
        """
        Execute operation with automatic retry on transient failures.

        Args:
            operation: Callable that returns (result, response_headers)
            should_retry: Optional predicate to determine if exception is retryable
                         Default: retry on RateLimitExceeded only

        Returns:
            Result from successful operation

        Raises:
            Exception: Last exception if all retries exhausted
        """
        if should_retry is None:
            should_retry = lambda e: isinstance(e, RateLimitExceeded)

        last_exception = None

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                # Check rate limit before attempting
                self.wait_if_needed()

                # Execute operation
                result, headers = operation()

                # Update rate limit from response
                self.update_rate_limit(headers)

                return result

            except Exception as e:
                last_exception = e

                # Update rate limit if available in exception
                if isinstance(e, RateLimitExceeded):
                    if e.reset_at:
                        if self._last_rate_limit:
                            self._last_rate_limit.reset_at = e.reset_at
                            self._last_rate_limit.remaining = None
                        else:
                            self._last_rate_limit = RateLimitInfo(
                                remaining=None,
                                reset_at=e.reset_at,
                            )
                    elif self._last_rate_limit is None:
                        self._last_rate_limit = RateLimitInfo()

                # Check if we should retry
                if not should_retry(e):
                    raise

                # Don't retry on last attempt
                if attempt >= self.retry_config.max_retries:
                    raise

                # Calculate and apply backoff when reset info unavailable
                delay = self.retry_config.calculate_delay(attempt)
                logger.info(
                    f"Retry attempt {attempt + 1}/{self.retry_config.max_retries} "
                    f"after {delay:.1f}s delay: {e}"
                )
                self.sleep(delay)

        # Should never reach here, but for type safety
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected retry loop exit")
