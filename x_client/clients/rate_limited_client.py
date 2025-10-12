"""
Rate-limited client wrapper for automatic retry on rate limit errors.

This module provides a decorator that wraps any X client to add
automatic retry with exponential backoff when rate limits are hit.
"""

from __future__ import annotations

from typing import Any, BinaryIO

from x_client.rate_limit import RateLimitHandler, RetryConfig


class RateLimitedClient:
    """
    Wrapper that adds rate limiting and retry logic to any X client.

    This decorator-style wrapper intercepts client calls and adds automatic
    retry with exponential backoff when rate limits are encountered.
    """

    def __init__(
        self,
        client: Any,
        retry_config: RetryConfig | None = None,
    ) -> None:
        """
        Initialize rate-limited client wrapper.

        Args:
            client: Underlying Twitter client (e.g., TweepyClient)
            retry_config: Optional retry configuration (uses defaults if not provided)
        """
        self._client = client
        self._handler = RateLimitHandler(
            retry_config=retry_config or RetryConfig()
        )

    def create_post(self, **kwargs: Any) -> Any:
        """Create post with automatic rate limit retry."""
        return self._execute_with_retry(
            lambda: self._client.create_post(**kwargs)
        )

    def delete_post(self, post_id: str) -> Any:
        """Delete post with automatic rate limit retry."""
        return self._execute_with_retry(
            lambda: self._client.delete_post(post_id)
        )

    def get_post(self, post_id: str, **kwargs: Any) -> Any:
        """Get post with automatic rate limit retry."""
        return self._execute_with_retry(
            lambda: self._client.get_post(post_id, **kwargs)
        )

    def search_recent_posts(self, query: str, **kwargs: Any) -> Any:
        """Search posts with automatic rate limit retry."""
        return self._execute_with_retry(
            lambda: self._client.search_recent_posts(query, **kwargs)
        )

    def upload_media(
        self,
        *,
        file: BinaryIO,
        media_category: str,
        mime_type: str | None = None,
        chunked: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Upload media with automatic rate limit retry."""
        return self._execute_with_retry(
            lambda: self._client.upload_media(
                file=file,
                media_category=media_category,
                mime_type=mime_type,
                chunked=chunked,
                **kwargs,
            )
        )

    def get_media_upload_status(self, media_id: str) -> Any:
        """Get media status with automatic rate limit retry."""
        return self._execute_with_retry(
            lambda: self._client.get_media_upload_status(media_id)
        )

    def _execute_with_retry(self, operation: Any) -> Any:
        """
        Execute operation with retry logic.

        Args:
            operation: Callable that performs the API operation

        Returns:
            Result from the operation

        Note:
            Since tweepy doesn't expose response headers on success,
            we can't track rate limits proactively. We rely on
            RateLimitExceeded exceptions for retry logic.
        """
        def wrapped_operation():
            # Execute operation (no headers available from tweepy on success)
            result = operation()
            # Return empty headers since tweepy doesn't expose them
            return result, {}

        return self._handler.execute_with_retry(wrapped_operation)

    def get_rate_limit_info(self):
        """Get current rate limit information (if available)."""
        return self._handler.get_rate_limit_info()
