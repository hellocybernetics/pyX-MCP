"""
Unit tests for MCP adapter.

Tests the XMCPAdapter class, verifying schema validation,
service integration, and error handling.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from x_client.exceptions import (
    ApiResponseError,
    AuthenticationError,
    ConfigurationError,
    MediaProcessingFailed,
    MediaValidationError,
    RateLimitExceeded,
)
from x_client.integrations.mcp_adapter import XMCPAdapter
from x_client.models import (
    MediaProcessingInfo,
    MediaUploadResult,
    Post,
)
from x_client.rate_limit import RateLimitInfo


@pytest.fixture
def mock_config():
    """Mock ConfigManager."""
    config = Mock()
    config.load_credentials = Mock()
    return config


@pytest.fixture
def mock_post_service():
    """Mock PostService."""
    service = Mock()
    service.client = Mock()
    return service


@pytest.fixture
def mock_media_service():
    """Mock MediaService."""
    return Mock()


@pytest.fixture
def adapter(mock_config, mock_post_service, mock_media_service):
    """Create XMCPAdapter with mocked dependencies."""
    return XMCPAdapter(
        config=mock_config,
        post_service=mock_post_service,
        media_service=mock_media_service,
    )


# ============================================================================
# Post Operations Tests
# ============================================================================


def test_create_post_success(adapter, mock_post_service):
    """Test successful post creation."""
    # Arrange
    mock_post = Post(
        id="1234567890",
        text="Hello, world!",
        author_id="author123",
        created_at=datetime(2025, 10, 12, 10, 30, 0, tzinfo=timezone.utc),
    )
    mock_post_service.create_post.return_value = mock_post

    request = {"text": "Hello, world!"}

    # Act
    result = adapter.create_post(request)

    # Assert
    assert result["id"] == "1234567890"
    assert result["text"] == "Hello, world!"
    assert result["author_id"] == "author123"
    assert result["created_at"] == "2025-10-12T10:30:00+00:00"
    mock_post_service.create_post.assert_called_once_with(
        text="Hello, world!",
        media_ids=None,
        in_reply_to=None,
        quote_post_id=None,
        reply_settings=None,
    )


def test_create_post_with_media(adapter, mock_post_service):
    """Test posting a post with media."""
    mock_post = Post(id="123", text="Photo", author_id="user1")
    mock_post_service.create_post.return_value = mock_post

    request = {
        "text": "Photo",
        "media_ids": ["media_001", "media_002"],
    }

    result = adapter.create_post(request)

    assert result["id"] == "123"
    mock_post_service.create_post.assert_called_once_with(
        text="Photo",
        media_ids=["media_001", "media_002"],
        in_reply_to=None,
        quote_post_id=None,
        reply_settings=None,
    )


def test_create_post_validation_error(adapter):
    """Test post creation with invalid request."""
    request = {}  # Missing required 'text' field

    result = adapter.create_post(request)

    # Should return ValidationError response
    assert result["error_type"] == "ValidationError"
    assert "validation failed" in result["message"]
    assert "details" in result
    assert "text" in result["details"]


def test_create_post_rate_limit_exceeded(adapter, mock_post_service):
    """Test post creation with rate limit error."""
    mock_post_service.create_post.side_effect = RateLimitExceeded(
        "Rate limit exceeded",
        reset_at=1728730800,  # Unix timestamp
    )

    request = {"text": "Test"}

    result = adapter.create_post(request)

    assert result["error_type"] == "RateLimitExceeded"
    assert "Rate limit exceeded" in result["message"]
    assert result["reset_at"] is not None


def test_delete_post_success(adapter, mock_post_service):
    """Test successful post deletion."""
    mock_post_service.delete_post.return_value = True

    request = {"post_id": "1234567890"}

    result = adapter.delete_post(request)

    assert result["deleted"] is True
    mock_post_service.delete_post.assert_called_once_with("1234567890")


def test_get_post_success(adapter, mock_post_service):
    """Test successful post retrieval."""
    mock_post = Post(
        id="1234567890",
        text="Test post",
        author_id="user123",
    )
    mock_post_service.get_post.return_value = mock_post

    request = {"post_id": "1234567890"}

    result = adapter.get_post(request)

    assert result["id"] == "1234567890"
    assert result["text"] == "Test post"
    mock_post_service.get_post.assert_called_once_with("1234567890")


def test_search_recent_posts_success(adapter, mock_post_service):
    """Test successful post search."""
    mock_posts = [
        Post(id="1", text="First post", author_id="user1"),
        Post(id="2", text="Second post", author_id="user2"),
    ]
    mock_post_service.search_recent.return_value = mock_posts

    request = {"query": "python", "max_results": 10}

    result = adapter.search_recent_posts(request)

    assert "posts" in result
    assert len(result["posts"]) == 2
    assert result["posts"][0]["id"] == "1"
    assert result["posts"][1]["id"] == "2"
    mock_post_service.search_recent.assert_called_once_with(
        query="python",
        max_results=10,
    )


# ============================================================================
# Media Operations Tests
# ============================================================================


def test_upload_image_success(adapter, mock_media_service, tmp_path):
    """Test successful image upload."""
    # Create a temporary image file
    image_file = tmp_path / "test.png"
    image_file.write_bytes(b"fake image data")

    mock_result = MediaUploadResult(
        media_id="9876543210",
        media_id_string="9876543210",
        expires_after_secs=86400,
    )
    mock_media_service.upload_image.return_value = mock_result

    request = {
        "path": str(image_file),
        "media_category": "post_image",
    }

    result = adapter.upload_image(request)

    assert result["media_id"] == "9876543210"
    assert result["expires_after_secs"] == 86400
    mock_media_service.upload_image.assert_called_once()
    call_args = mock_media_service.upload_image.call_args
    assert call_args[1]["path"] == Path(str(image_file))
    assert call_args[1]["media_category"] == "post_image"


def test_upload_video_success(adapter, mock_media_service, tmp_path):
    """Test successful video upload."""
    video_file = tmp_path / "test.mp4"
    video_file.write_bytes(b"fake video data")

    mock_result = MediaUploadResult(
        media_id="video123",
        media_id_string="video123",
        processing_info=MediaProcessingInfo(
            state="succeeded",
            progress_percent=100,
        ),
    )
    mock_media_service.upload_video.return_value = mock_result

    request = {
        "path": str(video_file),
        "media_category": "post_video",
        "poll_interval": 2.0,
        "timeout": 60.0,
    }

    result = adapter.upload_video(request)

    assert result["media_id"] == "video123"
    assert result["processing_info"]["state"] == "succeeded"
    assert result["processing_info"]["progress_percent"] == 100

    # Verify parameters are passed correctly
    mock_media_service.upload_video.assert_called_once()
    call_args = mock_media_service.upload_video.call_args
    assert call_args[1]["path"] == Path(str(video_file))
    assert call_args[1]["media_category"] == "post_video"
    assert call_args[1]["poll_interval"] == 2.0
    assert call_args[1]["timeout"] == 60.0


def test_upload_image_file_not_found(adapter):
    """Test image upload with non-existent file."""
    request = {
        "path": "/nonexistent/file.png",
    }

    # Should return ValidationError response
    result = adapter.upload_image(request)

    assert result["error_type"] == "ValidationError"
    assert "validation failed" in result["message"]
    assert "details" in result
    assert "path" in result["details"]


def test_upload_media_validation_error(adapter, mock_media_service, tmp_path):
    """Test media upload with validation error."""
    image_file = tmp_path / "test.png"
    image_file.write_bytes(b"fake")

    mock_media_service.upload_image.side_effect = MediaValidationError(
        "File size exceeds 5MB limit"
    )

    request = {"path": str(image_file)}

    result = adapter.upload_image(request)

    assert result["error_type"] == "MediaValidationError"
    assert "5MB" in result["message"]


# ============================================================================
# Authentication & Status Tests
# ============================================================================


def test_get_auth_status_authenticated(adapter, mock_config):
    """Test authentication status when authenticated."""
    from x_client.config import XCredentials

    mock_config.load_credentials.return_value = XCredentials(
        api_key="key",
        api_secret="secret",
        access_token="1234567890-token",
        access_token_secret="token_secret",
        bearer_token=None,
    )

    rate_limit = RateLimitInfo(limit=300, remaining=299, reset_at=1728730800)
    adapter.post_service.client.get_rate_limit_info.return_value = rate_limit

    request = {}

    result = adapter.get_auth_status(request)

    assert result["authenticated"] is True
    assert result["user_id"] == "1234567890"
    expected_reset = datetime.fromtimestamp(1728730800, tz=timezone.utc).isoformat()
    assert result["rate_limit"]["limit"] == 300
    assert result["rate_limit"]["remaining"] == 299
    assert result["rate_limit"]["reset_at"] == expected_reset


def test_get_auth_status_not_authenticated(adapter, mock_config):
    """Test authentication status when not authenticated."""
    mock_config.load_credentials.side_effect = ConfigurationError(
        "Missing credentials"
    )

    request = {}

    result = adapter.get_auth_status(request)

    assert result["authenticated"] is False
    assert "user_id" not in result
    assert "rate_limit" not in result
    adapter.post_service.client.get_rate_limit_info.assert_not_called()


# ============================================================================
# Error Handling Tests
# ============================================================================


def test_authentication_error_conversion(adapter, mock_post_service):
    """Test AuthenticationError conversion to ErrorResponse."""
    mock_post_service.create_post.side_effect = AuthenticationError(
        "Invalid token"
    )

    request = {"text": "Test"}

    result = adapter.create_post(request)

    assert result["error_type"] == "AuthenticationError"
    assert result["message"] == "Invalid token"
    # code is excluded by exclude_none=True if None
    assert "code" not in result or result["code"] is None


def test_api_response_error_conversion(adapter, mock_post_service):
    """Test ApiResponseError conversion to ErrorResponse."""
    mock_post_service.create_post.side_effect = ApiResponseError(
        "Forbidden",
        code=403,
    )

    request = {"text": "Test"}

    result = adapter.create_post(request)

    assert result["error_type"] == "ApiResponseError"
    assert result["message"] == "Forbidden"
    assert result["code"] == 403


# ============================================================================
# Tool Schema Tests
# ============================================================================


def test_get_tool_schemas(adapter):
    """Test getting JSON schemas for all tools."""
    schemas = adapter.get_tool_schemas()

    # Verify all expected tools are present
    expected_tools = [
        "create_post",
        "delete_post",
        "get_post",
        "search_recent_posts",
        "upload_image",
        "upload_video",
        "get_auth_status",
    ]

    for tool_name in expected_tools:
        assert tool_name in schemas
        assert "description" in schemas[tool_name]
        assert "input_schema" in schemas[tool_name]
        assert "output_schema" in schemas[tool_name]

    # Verify schema structure
    create_post_schema = schemas["create_post"]
    assert "text" in create_post_schema["input_schema"]["properties"]
    assert create_post_schema["input_schema"]["required"] == ["text"]
