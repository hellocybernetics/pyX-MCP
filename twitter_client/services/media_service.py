"""
Media upload workflows wrapping Twitter's chunked upload process.
"""

from __future__ import annotations

import mimetypes
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Callable, Protocol

from twitter_client.exceptions import (
    MediaProcessingFailed,
    MediaProcessingTimeout,
    MediaValidationError,
)
from twitter_client.models import MediaUploadResult

IMAGE_MAX_BYTES = 5 * 1024 * 1024
VIDEO_MAX_BYTES = 512 * 1024 * 1024
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_MIME_TYPES = {"video/mp4"}


class MediaClient(Protocol):
    """Protocol capturing media upload behaviour from client adapters."""

    def upload_media(
        self,
        *,
        file: BinaryIO,
        media_category: str,
        mime_type: str | None = None,
        **kwargs: Any,
    ) -> Any:
        ...

    def get_media_upload_status(self, media_id: str) -> Any:
        ...


@dataclass(slots=True)
class MediaService:
    """High level media upload orchestration with validation and polling."""

    client: MediaClient
    poll_interval: float = 2.0
    timeout: float = 60.0
    sleep: Callable[[float], None] = field(default=time.sleep)

    def upload_image(self, path: Path, *, media_category: str = "tweet_image") -> MediaUploadResult:
        """
        Upload image file (up to 5MB).

        Args:
            path: Path to image file (jpeg, png, webp, gif)
            media_category: Media category for Twitter API (default: tweet_image)

        Returns:
            MediaUploadResult with media_id

        Raises:
            MediaValidationError: If file size exceeds limit or MIME type unsupported
        """
        path = self._validate_path(path)
        mime_type = self._validate_image(path)
        # Images don't need chunked upload (all under 5MB limit)
        return self._upload(path, media_category=media_category, mime_type=mime_type, chunked=False)

    def upload_video(self, path: Path, *, media_category: str = "tweet_video") -> MediaUploadResult:
        """
        Upload video file (up to 512MB with chunked upload).

        Args:
            path: Path to video file (mp4)
            media_category: Media category for Twitter API (default: tweet_video)

        Returns:
            MediaUploadResult with media_id and processing_info

        Raises:
            MediaValidationError: If file size exceeds limit or MIME type unsupported
            MediaProcessingTimeout: If processing takes too long
            MediaProcessingFailed: If Twitter's processing fails
        """
        path = self._validate_path(path)
        mime_type = self._validate_video(path)
        # Videos require chunked upload for files >5MB (we enable it for all videos)
        return self._upload(path, media_category=media_category, mime_type=mime_type, chunked=True)

    def _upload(
        self,
        path: Path,
        *,
        media_category: str,
        mime_type: str | None,
        chunked: bool = False,
    ) -> MediaUploadResult:
        """
        Upload media file to Twitter API.

        Args:
            path: Path to media file
            media_category: tweet_image, tweet_gif, or tweet_video
            mime_type: MIME type of the file
            chunked: Enable chunked upload (required for videos >5MB)

        Returns:
            MediaUploadResult with media_id and processing status
        """
        with path.open("rb") as file_obj:
            response = self.client.upload_media(
                file=file_obj,
                media_category=media_category,
                mime_type=mime_type,
                chunked=chunked,
            )
        result = MediaUploadResult.from_api(response)
        return self._await_processing(result)

    def _await_processing(self, result: MediaUploadResult) -> MediaUploadResult:
        info = result.processing_info
        if info is None:
            return result

        if info.state.lower() == "failed":
            raise MediaProcessingFailed(
                info.error.message if info.error else "Media processing failed.",
                code=info.error.code if info.error else None,
            )

        if info.state.lower() in {"succeeded", "success"}:
            return result

        status_fetcher = getattr(self.client, "get_media_upload_status", None)
        if status_fetcher is None:
            raise MediaProcessingTimeout("Media processing is still in progress.")

        deadline = time.monotonic() + self.timeout
        current = result
        while info and info.state.lower() in {"pending", "in_progress"}:
            wait_seconds = info.check_after_secs or self.poll_interval
            if time.monotonic() + wait_seconds > deadline:
                raise MediaProcessingTimeout("Timed out waiting for media processing to complete.")
            self.sleep(wait_seconds)
            refreshed = MediaUploadResult.from_api(status_fetcher(current.media_id))
            info = refreshed.processing_info
            current = refreshed

            if info and info.state.lower() == "failed":
                raise MediaProcessingFailed(
                    info.error.message if info.error else "Media processing failed.",
                    code=info.error.code if info.error else None,
                )

        if info and info.state.lower() not in {"succeeded", "success"}:
            raise MediaProcessingTimeout("Media processing did not complete successfully.")

        return current

    @staticmethod
    def _validate_path(path: Path) -> Path:
        resolved = path.expanduser()
        if not resolved.exists() or not resolved.is_file():
            raise MediaValidationError(f"Media file '{path}' does not exist or is not a file.")
        return resolved

    @staticmethod
    def _validate_image(path: Path) -> str:
        size = path.stat().st_size
        if size > IMAGE_MAX_BYTES:
            raise MediaValidationError(
                f"Image '{path}' exceeds the {IMAGE_MAX_BYTES} byte size limit."
            )
        mime_type, _ = mimetypes.guess_type(path.name)
        if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
            raise MediaValidationError(
                f"Unsupported image MIME type '{mime_type}' for '{path.name}'."
            )
        return mime_type

    @staticmethod
    def _validate_video(path: Path) -> str:
        size = path.stat().st_size
        if size > VIDEO_MAX_BYTES:
            raise MediaValidationError(
                f"Video '{path}' exceeds the {VIDEO_MAX_BYTES} byte size limit."
            )
        mime_type, _ = mimetypes.guess_type(path.name)
        if mime_type not in ALLOWED_VIDEO_MIME_TYPES:
            raise MediaValidationError(
                f"Unsupported video MIME type '{mime_type}' for '{path.name}'."
            )
        return mime_type
