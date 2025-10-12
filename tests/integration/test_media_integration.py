"""Integration tests for end-to-end media upload workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

from x_client.clients.tweepy_client import TweepyClient
from x_client.config import XCredentials
from x_client.exceptions import MediaValidationError
from x_client.factory import XClientFactory
from x_client.services.media_service import MediaService


@pytest.fixture
def credentials() -> XCredentials:
    """Provide valid test credentials."""
    return XCredentials(
        api_key="test_api_key",
        api_secret="test_api_secret",
        access_token="test_access_token",
        access_token_secret="test_access_token_secret",
    )


@pytest.fixture
def client(credentials: XCredentials) -> TweepyClient:
    """Create TweepyClient with test credentials."""
    return XClientFactory.create_from_credentials(credentials)


@pytest.fixture
def media_service(client: TweepyClient) -> MediaService:
    """Create MediaService with TweepyClient."""
    return MediaService(client, sleep=lambda _: None, poll_interval=0, timeout=5)


def _write_file(path: Path, size: int) -> None:
    """Helper to create test files."""
    path.write_bytes(b"\0" * size)


def test_media_service_initialization(credentials: XCredentials) -> None:
    """Integration: MediaService properly initializes with factory client."""
    client = XClientFactory.create_from_credentials(credentials)
    media_service = MediaService(client)

    assert media_service.client is client
    assert hasattr(media_service, "upload_image")
    assert hasattr(media_service, "upload_video")


def test_media_service_has_upload_methods(media_service: MediaService) -> None:
    """Integration: MediaService exposes upload methods."""
    assert hasattr(media_service, "upload_image")
    assert hasattr(media_service, "upload_video")
    assert hasattr(media_service, "_upload")
    assert hasattr(media_service, "_await_processing")


def test_upload_image_size_validation(media_service: MediaService, tmp_path: Path) -> None:
    """Integration test: Image size validation."""
    large_image = tmp_path / "large.png"
    _write_file(large_image, 6 * 1024 * 1024)  # 6MB > 5MB limit

    with pytest.raises(MediaValidationError) as exc_info:
        media_service.upload_image(large_image)

    assert "exceeds" in str(exc_info.value)


def test_upload_unsupported_mime_type(media_service: MediaService, tmp_path: Path) -> None:
    """Integration test: Unsupported MIME type validation."""
    bad_file = tmp_path / "test.bmp"
    _write_file(bad_file, 1024)

    with pytest.raises(MediaValidationError) as exc_info:
        media_service.upload_image(bad_file)

    assert "Unsupported" in str(exc_info.value)


def test_upload_nonexistent_file(media_service: MediaService, tmp_path: Path) -> None:
    """Integration test: File existence validation."""
    nonexistent = tmp_path / "nonexistent.png"

    with pytest.raises(MediaValidationError) as exc_info:
        media_service.upload_image(nonexistent)

    assert "does not exist" in str(exc_info.value)
