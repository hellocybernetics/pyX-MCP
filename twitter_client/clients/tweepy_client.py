"""
Thin wrapper around tweepy.Client to present a consistent interface.
"""

from __future__ import annotations

from typing import Any, BinaryIO

import tweepy

from twitter_client.exceptions import ApiResponseError, RateLimitExceeded

try:  # pragma: no cover - defensive import
    TweepyErrors = tweepy.errors  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover
    TweepyErrors = None

if TweepyErrors is not None:
    TweepyException = TweepyErrors.TweepyException
    TooManyRequests = getattr(TweepyErrors, "TooManyRequests", TweepyErrors.TweepyException)
else:  # pragma: no cover
    TweepyException = tweepy.TweepError  # type: ignore[attr-defined]
    TooManyRequests = TweepyException


class TweepyClient:
    """Wrapper that converts tweepy exceptions into domain exceptions."""

    def __init__(self, client: tweepy.Client) -> None:
        self._client = client

    def create_tweet(self, **kwargs: Any) -> Any:
        return self._invoke("create_tweet", **kwargs)

    def delete_tweet(self, tweet_id: str) -> Any:
        return self._invoke("delete_tweet", tweet_id)

    def get_tweet(self, tweet_id: str, **kwargs: Any) -> Any:
        return self._invoke("get_tweet", tweet_id, **kwargs)

    def search_recent_tweets(self, query: str, **kwargs: Any) -> Any:
        return self._invoke("search_recent_tweets", query, **kwargs)

    def upload_media(
        self,
        *,
        file: BinaryIO,
        media_category: str,
        mime_type: str | None = None,
        **kwargs: Any,
    ) -> Any:
        payload = {"file": file, "media_category": media_category, **kwargs}
        if mime_type:
            payload["mime_type"] = mime_type
        return self._invoke("upload_media", **payload)

    def get_media_upload_status(self, media_id: str) -> Any:
        if hasattr(self._client, "get_media_upload_status"):
            return self._invoke("get_media_upload_status", media_id)
        if hasattr(self._client, "get_media"):
            return self._invoke("get_media", media_id)
        raise AttributeError("tweepy.Client has no media status retrieval method.")

    def _invoke(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        method = getattr(self._client, method_name, None)
        if method is None:
            raise AttributeError(f"tweepy.Client has no attribute '{method_name}'.")

        try:
            return method(*args, **kwargs)
        except TweepyException as exc:
            raise self._convert_exception(exc) from exc

    def _convert_exception(self, exc: TweepyException) -> ApiResponseError:
        message = str(exc) or "Unhandled Tweepy exception."

        if isinstance(exc, TooManyRequests):
            reset_at = self._extract_reset_at(exc)
            return RateLimitExceeded(message, reset_at=reset_at)

        api_codes = getattr(exc, "api_codes", None)
        code: int | None = api_codes[0] if api_codes else None
        return ApiResponseError(message, code=code)

    @staticmethod
    def _extract_reset_at(exc: TweepyException) -> int | None:
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None)
        if not headers:
            return None

        reset_value = headers.get("x-rate-limit-reset") or headers.get(
            "X-Rate-Limit-Reset"
        )
        if reset_value is None:
            return None

        try:
            return int(reset_value)
        except (TypeError, ValueError):
            return None
