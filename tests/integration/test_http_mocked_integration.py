"""Integration tests with HTTP mocking using responses library."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import responses

from twitter_client.config import ConfigManager, TwitterCredentials
from twitter_client.factory import TwitterClientFactory
from twitter_client.services.media_service import MediaService
from twitter_client.services.tweet_service import TweetService

from .fixtures import (
    MEDIA_UPLOAD_IMAGE_RESPONSE,
    MEDIA_UPLOAD_VIDEO_FINALIZE_RESPONSE,
    MEDIA_UPLOAD_VIDEO_INIT_RESPONSE,
    MEDIA_UPLOAD_VIDEO_STATUS_SUCCEEDED,
    TWEET_RESPONSE,
)


@pytest.fixture
def credentials() -> TwitterCredentials:
    """Provide test credentials."""
    return TwitterCredentials(
        api_key="test_api_key",
        api_secret="test_api_secret",
        access_token="test_access_token",
        access_token_secret="test_access_token_secret",
        bearer_token="test_bearer_token",
    )


@pytest.fixture
def mock_image_file(tmp_path: Path) -> Path:
    """Create a temporary PNG file for testing."""
    file_path = tmp_path / "test_image.png"
    file_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 100)  # Valid PNG header + data
    return file_path


@pytest.fixture
def mock_video_file(tmp_path: Path) -> Path:
    """Create a temporary MP4 file for testing."""
    file_path = tmp_path / "test_video.mp4"
    file_path.write_bytes(b"\0" * 1024)  # Small video data
    return file_path


@responses.activate
def test_create_tweet_with_real_http_mocking(credentials: TwitterCredentials) -> None:
    """Integration: Create tweet with actual HTTP request mocking."""
    # Mock Twitter API v2 endpoint
    responses.add(
        responses.POST,
        "https://api.twitter.com/2/tweets",
        json=TWEET_RESPONSE,
        status=201,
    )

    # Create client and service
    client = TwitterClientFactory.create_from_credentials(credentials)
    tweet_service = TweetService(client)

    # Create tweet
    tweet = tweet_service.create_tweet(text="Hello from HTTP mocked test!")

    # Verify response
    assert tweet.id == "1234567890"
    assert tweet.text == "Hello from integration test!"

    # Verify HTTP call was made
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == "https://api.twitter.com/2/tweets"


@responses.activate
def test_upload_image_with_http_mocking(
    credentials: TwitterCredentials,
    mock_image_file: Path,
) -> None:
    """Integration: Upload image with HTTP request mocking."""
    # Mock Twitter API v1.1 media upload endpoint
    responses.add(
        responses.POST,
        "https://upload.twitter.com/1.1/media/upload.json",
        json=MEDIA_UPLOAD_IMAGE_RESPONSE,
        status=200,
    )

    # Create client and service
    client = TwitterClientFactory.create_from_credentials(credentials)
    media_service = MediaService(client)

    # Upload image
    result = media_service.upload_image(mock_image_file)

    # Verify response
    assert result.media_id == "1234567890123456789"

    # Verify HTTP call was made
    assert len(responses.calls) == 1
    assert "upload.twitter.com" in responses.calls[0].request.url


@pytest.mark.skip(reason="tweepy internal API conflict with media_type parameter in chunked upload")
@responses.activate
def test_upload_video_with_chunked_upload_mocking(
    credentials: TwitterCredentials,
    mock_video_file: Path,
) -> None:
    """Integration: Upload video with chunked upload HTTP mocking."""
    # Mock video upload flow: INIT → APPEND → FINALIZE → STATUS
    responses.add(
        responses.POST,
        "https://upload.twitter.com/1.1/media/upload.json",
        json=MEDIA_UPLOAD_VIDEO_INIT_RESPONSE,
        status=200,
    )
    responses.add(
        responses.POST,
        "https://upload.twitter.com/1.1/media/upload.json",
        json={},  # APPEND returns empty response
        status=204,
    )
    responses.add(
        responses.POST,
        "https://upload.twitter.com/1.1/media/upload.json",
        json=MEDIA_UPLOAD_VIDEO_FINALIZE_RESPONSE,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://upload.twitter.com/1.1/media/upload.json",
        json=MEDIA_UPLOAD_VIDEO_STATUS_SUCCEEDED,
        status=200,
    )

    # Create client and service with minimal polling delay
    client = TwitterClientFactory.create_from_credentials(credentials)
    media_service = MediaService(client, poll_interval=0, timeout=10)

    # Upload video
    result = media_service.upload_video(mock_video_file)

    # Verify response
    assert result.media_id == "9876543210987654321"
    assert result.processing_info is not None
    assert result.processing_info.state == "succeeded"

    # Verify chunked upload flow: INIT + APPEND + FINALIZE + STATUS
    assert len(responses.calls) >= 3  # At least INIT, APPEND, FINALIZE


@responses.activate
def test_end_to_end_tweet_with_image(
    credentials: TwitterCredentials,
    mock_image_file: Path,
) -> None:
    """Integration: End-to-end tweet creation with image upload."""
    # Mock media upload
    responses.add(
        responses.POST,
        "https://upload.twitter.com/1.1/media/upload.json",
        json=MEDIA_UPLOAD_IMAGE_RESPONSE,
        status=200,
    )

    # Mock tweet creation
    tweet_response_with_media = {
        "data": {
            "id": "9999999999",
            "text": "Check out this image!",
            "edit_history_tweet_ids": ["9999999999"],
        }
    }
    responses.add(
        responses.POST,
        "https://api.twitter.com/2/tweets",
        json=tweet_response_with_media,
        status=201,
    )

    # Create services
    client = TwitterClientFactory.create_from_credentials(credentials)
    media_service = MediaService(client)
    tweet_service = TweetService(client)

    # Upload image
    media_result = media_service.upload_image(mock_image_file)

    # Create tweet with media
    tweet = tweet_service.create_tweet(
        text="Check out this image!",
        media_ids=[media_result.media_id],
    )

    # Verify end-to-end flow
    assert media_result.media_id == "1234567890123456789"
    assert tweet.id == "9999999999"
    assert len(responses.calls) == 2  # Media upload + tweet creation


@responses.activate
def test_factory_initialization_with_config(tmp_path: Path) -> None:
    """Integration: Factory creates client from ConfigManager with HTTP mocking."""
    # Create config file
    config_file = tmp_path / "twitter_config.json"
    config_data = {
        "api_key": "test_key",
        "api_secret": "test_secret",
        "access_token": "test_token",
        "access_token_secret": "test_token_secret",
        "bearer_token": "test_bearer",
    }
    config_file.write_text(json.dumps(config_data))

    # Mock API call
    responses.add(
        responses.POST,
        "https://api.twitter.com/2/tweets",
        json=TWEET_RESPONSE,
        status=201,
    )

    # Load config and create client
    config = ConfigManager(credential_path=config_file)
    client = TwitterClientFactory.create_from_config(config)
    tweet_service = TweetService(client)

    # Create tweet to verify client works
    tweet = tweet_service.create_tweet(text="Factory test")

    assert tweet.id == "1234567890"
    assert len(responses.calls) == 1
