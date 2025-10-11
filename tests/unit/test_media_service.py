from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from twitter_client.exceptions import (
    MediaProcessingFailed,
    MediaProcessingTimeout,
    MediaValidationError,
)
from twitter_client.models import MediaUploadResult
from twitter_client.services.media_service import IMAGE_MAX_BYTES, MediaService


class FakeMediaClient:
    def __init__(self, *, upload_response: dict[str, object], status_responses: list[dict[str, object]] | None = None) -> None:
        self.upload_calls: list[dict[str, object]] = []
        self.status_calls: list[str] = []
        self.upload_response = upload_response
        self.status_responses = status_responses or []
        self._status_index = 0

    def upload_media(self, *, file, media_category, mime_type=None, chunked=False, **kwargs):
        self.upload_calls.append(
            {
                "media_category": media_category,
                "mime_type": mime_type,
                "chunked": chunked,
                "extra": kwargs,
                "closed": file.closed,
            }
        )
        return self.upload_response

    def get_media_upload_status(self, media_id: str):
        self.status_calls.append(media_id)
        if self._status_index >= len(self.status_responses):
            return self.upload_response
        response = self.status_responses[self._status_index]
        self._status_index += 1
        return response


def _write_file(path: Path, size: int) -> None:
    path.write_bytes(b"\0" * size)


def test_upload_image_validates_and_returns_result(tmp_path: Path) -> None:
    file_path = tmp_path / "image.png"
    _write_file(file_path, 1024)
    upload_response = {
        "media_id": "1",
        "media_key": "3_1",
        "processing_info": {"state": "succeeded"},
    }
    client = FakeMediaClient(upload_response=upload_response)
    service = MediaService(client, sleep=lambda _: None)

    result = service.upload_image(file_path)

    assert result.media_id == "1"
    assert client.upload_calls[0]["media_category"] == "tweet_image"
    assert client.upload_calls[0]["mime_type"] == "image/png"
    assert client.upload_calls[0]["chunked"] is False  # Images don't need chunked


def test_upload_image_rejects_large_files(tmp_path: Path) -> None:
    file_path = tmp_path / "big.png"
    _write_file(file_path, IMAGE_MAX_BYTES + 1)
    client = FakeMediaClient(upload_response={"media_id": "ignored"})
    service = MediaService(client)

    with pytest.raises(MediaValidationError):
        service.upload_image(file_path)


def test_upload_video_polls_until_success(tmp_path: Path) -> None:
    file_path = tmp_path / "movie.mp4"
    _write_file(file_path, 2048)
    upload_response = {
        "media_id": "42",
        "processing_info": {"state": "pending", "check_after_secs": 0},
    }
    status_responses = [
        {"media_id": "42", "processing_info": {"state": "in_progress", "check_after_secs": 0}},
        {"media_id": "42", "processing_info": {"state": "succeeded"}},
    ]
    client = FakeMediaClient(upload_response=upload_response, status_responses=status_responses)
    service = MediaService(client, sleep=lambda _: None, poll_interval=0, timeout=5)

    result = service.upload_video(file_path)

    assert result.processing_info is not None
    assert result.processing_info.state.lower() == "succeeded"
    assert client.status_calls == ["42", "42"]
    # Verify chunked upload is enabled for videos
    assert client.upload_calls[0]["chunked"] is True
    assert client.upload_calls[0]["mime_type"] == "video/mp4"


def test_upload_video_raises_on_processing_failure(tmp_path: Path) -> None:
    file_path = tmp_path / "movie.mp4"
    _write_file(file_path, 2048)
    upload_response = {
        "media_id": "999",
        "processing_info": {
            "state": "failed",
            "error": {"message": "encoding failed", "code": 1200},
        },
    }
    client = FakeMediaClient(upload_response=upload_response)
    service = MediaService(client)

    with pytest.raises(MediaProcessingFailed) as exc:
        service.upload_video(file_path)

    assert "encoding failed" in str(exc.value)


def test_upload_video_times_out_when_processing_hangs(tmp_path: Path) -> None:
    file_path = tmp_path / "movie.mp4"
    _write_file(file_path, 2048)
    upload_response = {
        "media_id": "555",
        "processing_info": {"state": "pending", "check_after_secs": 5},
    }
    client = FakeMediaClient(upload_response=upload_response)
    service = MediaService(client, sleep=lambda _: None, poll_interval=0.1, timeout=1)

    with pytest.raises(MediaProcessingTimeout):
        service.upload_video(file_path)


def test_upload_gif_routes_to_tweet_gif_with_chunked(tmp_path: Path) -> None:
    """GIF images are automatically routed to tweet_gif category with chunked upload."""
    file_path = tmp_path / "animation.gif"
    _write_file(file_path, 1024)
    upload_response = {
        "media_id": "123",
        "media_key": "3_123",
        "processing_info": {"state": "succeeded"},
    }
    client = FakeMediaClient(upload_response=upload_response)
    service = MediaService(client, sleep=lambda _: None)

    result = service.upload_image(file_path)

    assert result.media_id == "123"
    # Verify GIF is routed to tweet_gif category (not tweet_image)
    assert client.upload_calls[0]["media_category"] == "tweet_gif"
    assert client.upload_calls[0]["mime_type"] == "image/gif"
    # Verify chunked upload is enabled for GIFs
    assert client.upload_calls[0]["chunked"] is True


def test_upload_gif_ignores_media_category_parameter(tmp_path: Path) -> None:
    """GIF images ignore media_category parameter and always use tweet_gif."""
    file_path = tmp_path / "animation.gif"
    _write_file(file_path, 1024)
    upload_response = {
        "media_id": "456",
        "processing_info": {"state": "succeeded"},
    }
    client = FakeMediaClient(upload_response=upload_response)
    service = MediaService(client, sleep=lambda _: None)

    # User explicitly passes tweet_image, but GIF should override to tweet_gif
    result = service.upload_image(file_path, media_category="tweet_image")

    assert result.media_id == "456"
    # Verify parameter is ignored for GIFs
    assert client.upload_calls[0]["media_category"] == "tweet_gif"
    assert client.upload_calls[0]["chunked"] is True


def test_polling_configuration_is_customizable(tmp_path: Path) -> None:
    """MediaService polling parameters can be configured via constructor."""
    file_path = tmp_path / "movie.mp4"
    _write_file(file_path, 2048)
    upload_response = {
        "media_id": "999",
        "processing_info": {"state": "pending", "check_after_secs": 0},
    }
    status_responses = [
        {"media_id": "999", "processing_info": {"state": "succeeded"}},
    ]
    client = FakeMediaClient(upload_response=upload_response, status_responses=status_responses)

    # Custom polling configuration
    custom_poll_interval = 10.0
    custom_timeout = 300.0
    service = MediaService(
        client,
        sleep=lambda _: None,
        poll_interval=custom_poll_interval,
        timeout=custom_timeout,
    )

    result = service.upload_video(file_path)

    # Verify configuration is applied
    assert service.poll_interval == custom_poll_interval
    assert service.timeout == custom_timeout
    assert result.media_id == "999"


def test_polling_uses_default_values_when_not_specified(tmp_path: Path) -> None:
    """MediaService uses default polling values when not explicitly configured."""
    file_path = tmp_path / "movie.mp4"
    _write_file(file_path, 2048)
    upload_response = {"media_id": "123", "processing_info": {"state": "succeeded"}}
    client = FakeMediaClient(upload_response=upload_response)

    # Use default configuration (no parameters specified)
    service = MediaService(client, sleep=lambda _: None)

    result = service.upload_video(file_path)

    # Verify default values are used
    assert service.poll_interval == 2.0  # Default from dataclass
    assert service.timeout == 60.0  # Default from dataclass
    assert result.media_id == "123"
