"""
Dual wrapper around tweepy.Client (v2) and tweepy.API (v1.1).

This module provides a unified interface for Twitter operations:
- Tweet operations use tweepy.Client (v2 API)
- Media upload uses tweepy.API (v1.1 API) since v2 has no media endpoints
"""

from __future__ import annotations

from typing import Any, BinaryIO

import tweepy

from x_client.exceptions import ApiResponseError, RateLimitExceeded

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
    """
    Dual-client wrapper for Twitter API operations.

    Uses tweepy.Client (v2 API) for tweet operations and tweepy.API (v1.1)
    for media upload, presenting a unified interface to service layers.
    """

    def __init__(self, v2_client: tweepy.Client, v1_api: tweepy.API) -> None:
        """
        Initialize dual-client wrapper.

        Args:
            v2_client: tweepy.Client instance for v2 API operations (tweets)
            v1_api: tweepy.API instance for v1.1 API operations (media)
        """
        self._client = v2_client
        self._api = v1_api

    def create_post(self, **kwargs: Any) -> Any:
        return self._invoke("create_tweet", **kwargs)

    def delete_post(self, post_id: str) -> Any:
        return self._invoke("delete_tweet", post_id)

    def get_post(self, post_id: str, **kwargs: Any) -> Any:
        return self._invoke("get_tweet", post_id, **kwargs)

    def search_recent_posts(self, query: str, **kwargs: Any) -> Any:
        return self._invoke("search_recent_tweets", query, **kwargs)

    def repost_post(self, post_id: str) -> Any:
        return self._invoke("retweet", tweet_id=post_id, user_auth=True)

    def undo_repost(self, post_id: str) -> Any:
        return self._invoke("unretweet", tweet_id=post_id, user_auth=True)

    def upload_media(
        self,
        *,
        file: BinaryIO,
        media_category: str,
        mime_type: str | None = None,
        chunked: bool = False,
        **kwargs: Any,
    ) -> Any:
        """
        Upload media using v1.1 API.

        Routes to tweepy.API.media_upload() which supports chunked upload
        for large files (videos). For videos >5MB, chunked=True is required.

        Args:
            file: Binary file object to upload
            media_category: post_image, post_gif, or post_video
            mime_type: MIME type (e.g., image/png, video/mp4)
            chunked: Enable chunked upload for large files (required for videos >5MB)
            **kwargs: Additional parameters passed to Twitter API

        Returns:
            Media upload response with media_id and processing_info
        """
        try:
            # Simple uploads (images <=5MB) work best with Tweepy handling file IO.
            if not chunked:
                upload_kwargs = {}
                if media_category:
                    upload_kwargs["media_category"] = media_category
                return self._api.media_upload(
                    filename=getattr(file, "name", "media"),
                    **upload_kwargs,
                )

            # Chunked uploads (GIF/video) require explicit streaming.
            upload_kwargs = {
                "media_category": media_category,
                "chunked": True,
            }
            if mime_type:
                upload_kwargs["media_type"] = mime_type
            upload_kwargs.update(kwargs)

            # Tweepy expects file-like object for chunked uploads.
            return self._api.media_upload(
                filename=getattr(file, "name", "media"),
                file=file,
                **upload_kwargs,
            )
        except TweepyException as exc:
            raise self._convert_exception(exc) from exc

    def get_media_upload_status(self, media_id: str) -> Any:
        """
        Get media processing status using v1.1 API.

        Args:
            media_id: Media ID returned from upload_media

        Returns:
            Media status object with processing_info
        """
        try:
            return self._api.get_media_upload_status(media_id)
        except TweepyException as exc:
            raise self._convert_exception(exc) from exc

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
