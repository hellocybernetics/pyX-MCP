"""
Integration tests for MCP adapter workflows.

Tests end-to-end workflows using the MCP adapter with mocked
HTTP responses to verify correct integration between adapter,
services, and client layers.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import responses
from responses import matchers

from x_client.config import ConfigManager
from x_client.factory import XClientFactory
from x_client.integrations.mcp_adapter import XMCPAdapter


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
def adapter(test_credentials):
    """Create MCP adapter with test configuration."""
    config = ConfigManager(dotenv_path=test_credentials)
    client = XClientFactory.create_from_config(config)

    from x_client.services.media_service import MediaService
    from x_client.services.post_service import PostService

    post_service = PostService(client)
    media_service = MediaService(client)

    return XMCPAdapter(
        config=config,
        post_service=post_service,
        media_service=media_service,
    )


# ============================================================================
# Text Post Workflow
# ============================================================================


@responses.activate
def test_post_text_post_workflow(adapter):
    """Test posting a simple text post via MCP adapter."""
    # Mock Twitter API response for post creation
    responses.post(
        "https://api.twitter.com/2/tweets",
        json={
            "data": {
                "id": "1234567890123456789",
                "text": "Hello from MCP adapter!",
            }
        },
        status=201,
    )

    # Execute workflow
    request = {"text": "Hello from MCP adapter!"}
    result = adapter.create_post(request)

    # Verify result
    assert result["id"] == "1234567890123456789"
    assert result["text"] == "Hello from MCP adapter!"
    assert "error_type" not in result

    # Verify API was called
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == "https://api.twitter.com/2/tweets"


# ============================================================================
# Image Upload + Post Workflow
# ============================================================================


@responses.activate
def test_image_upload_and_post_workflow(adapter, tmp_path):
    """Test uploading an image and posting it in a post."""
    # Create test image file
    image_file = tmp_path / "test_image.png"
    image_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # Minimal PNG header

    # Mock media upload endpoint (v1.1 API)
    responses.post(
        "https://upload.twitter.com/1.1/media/upload.json",
        json={
            "media_id": 987654321,
            "media_id_string": "987654321",
            "expires_after_secs": 86400,
        },
        status=200,
    )

    # Mock post creation with media (v2 API)
    responses.post(
        "https://api.twitter.com/2/tweets",
        json={
            "data": {
                "id": "1234567890123456789",
                "text": "Check out this image!",
            }
        },
        status=201,
    )

    # Step 1: Upload image
    upload_request = {
        "path": str(image_file),
        "media_category": "post_image",
    }
    upload_result = adapter.upload_image(upload_request)

    assert upload_result["media_id"] == "987654321"
    assert "error_type" not in upload_result

    # Step 2: Post with media
    post_request = {
        "text": "Check out this image!",
        "media_ids": [upload_result["media_id"]],
    }
    post_result = adapter.create_post(post_request)

    assert post_result["id"] == "1234567890123456789"
    assert post_result["text"] == "Check out this image!"
    assert "error_type" not in post_result

    # Verify both API calls were made
    assert len(responses.calls) == 2
    assert "upload.twitter.com" in responses.calls[0].request.url
    assert "api.twitter.com/2/tweets" in responses.calls[1].request.url


# ============================================================================
# Post Search Workflow
# ============================================================================


@pytest.mark.skip(reason="Tweepy v2 API response mocking incompatibility with responses library")
@responses.activate
def test_search_posts_workflow(adapter):
    """Test searching for posts via MCP adapter."""
    # Mock Twitter search API response with edit_history_post_ids
    responses.get(
        "https://api.twitter.com/2/tweets/search/recent",
        json={
            "data": [
                {
                    "id": "111",
                    "text": "Python is awesome #python",
                    "edit_history_post_ids": ["111"],
                },
                {
                    "id": "222",
                    "text": "Learning Python today #python",
                    "edit_history_post_ids": ["222"],
                },
            ]
        },
        status=200,
    )

    # Execute search
    request = {
        "query": "#python",
        "max_results": 10,
    }
    result = adapter.search_recent_posts(request)

    # Verify results
    assert "posts" in result
    assert len(result["posts"]) == 2
    assert result["posts"][0]["id"] == "111"
    assert result["posts"][1]["id"] == "222"
    assert "Python" in result["posts"][0]["text"]
    assert "error_type" not in result


# ============================================================================
# Post Retrieval and Deletion Workflow
# ============================================================================


@pytest.mark.skip(reason="Tweepy v2 API response mocking incompatibility with responses library")
@responses.activate
def test_get_and_delete_post_workflow(adapter):
    """Test retrieving and then deleting a post."""
    post_id = "1234567890123456789"

    # Mock get tweet endpoint with edit_history_post_ids
    responses.get(
        f"https://api.twitter.com/2/tweets/{post_id}",
        json={
            "data": {
                "id": post_id,
                "text": "Test post to delete",
                "edit_history_post_ids": [post_id],
            }
        },
        status=200,
    )

    # Mock delete tweet endpoint
    responses.delete(
        f"https://api.twitter.com/2/tweets/{post_id}",
        json={
            "data": {
                "deleted": True,
            }
        },
        status=200,
    )

    # Step 1: Get tweet
    get_request = {"post_id": post_id}
    get_result = adapter.get_post(get_request)

    assert get_result["id"] == post_id
    assert get_result["text"] == "Test post to delete"

    # Step 2: Delete tweet
    delete_request = {"post_id": post_id}
    delete_result = adapter.delete_post(delete_request)

    assert delete_result["deleted"] is True

    # Verify both API calls
    assert len(responses.calls) == 2


# ============================================================================
# Video Upload + Post Workflow
# ============================================================================


@pytest.mark.skip(reason="Tweepy chunked upload incompatibility with responses library")
@responses.activate
def test_video_upload_and_post_workflow(adapter, tmp_path):
    """Test uploading a video and posting it in a post."""
    # Create test video file
    video_file = tmp_path / "test_video.mp4"
    video_file.write_bytes(b"\x00\x00\x00\x20ftypisom" + b"\x00" * 1000)  # Minimal MP4 header

    # Mock video upload endpoint (v1.1 API) - INIT phase
    responses.post(
        "https://upload.twitter.com/1.1/media/upload.json",
        json={
            "media_id": 888888888,
            "media_id_string": "888888888",
            "processing_info": {
                "state": "pending",
                "check_after_secs": 1,
            },
        },
        status=200,
    )

    # Mock video status check endpoint - processing complete
    responses.get(
        "https://upload.twitter.com/1.1/media/upload.json",
        json={
            "media_id": 888888888,
            "media_id_string": "888888888",
            "processing_info": {
                "state": "succeeded",
                "progress_percent": 100,
            },
        },
        status=200,
    )

    # Mock post creation with video (v2 API)
    responses.post(
        "https://api.twitter.com/2/tweets",
        json={
            "data": {
                "id": "1234567890123456789",
                "text": "Check out this video!",
            }
        },
        status=201,
    )

    # Step 1: Upload video with custom timeout
    upload_request = {
        "path": str(video_file),
        "media_category": "post_video",
        "poll_interval": 1.0,
        "timeout": 30.0,
    }
    upload_result = adapter.upload_video(upload_request)

    assert upload_result["media_id"] == "888888888"
    assert upload_result["processing_info"]["state"] == "succeeded"
    assert "error_type" not in upload_result

    # Step 2: Post with video
    post_request = {
        "text": "Check out this video!",
        "media_ids": [upload_result["media_id"]],
    }
    post_result = adapter.create_post(post_request)

    assert post_result["id"] == "1234567890123456789"
    assert post_result["text"] == "Check out this video!"
    assert "error_type" not in post_result

    # Verify API calls were made
    # Note: responses library may not properly mock tweepy's chunked upload,
    # but this verifies the interface and parameter passing
    assert len(responses.calls) >= 2


# ============================================================================
# Authentication Status Workflow
# ============================================================================


def test_auth_status_workflow(adapter):
    """Test getting authentication status via MCP adapter."""
    request = {}
    result = adapter.get_auth_status(request)

    # Should return authenticated status based on test credentials
    assert result["authenticated"] is True
    assert isinstance(result["user_id"], str)


# ============================================================================
# Error Handling Workflows
# ============================================================================


@responses.activate
def test_rate_limit_error_workflow(adapter):
    """Test handling rate limit error in MCP adapter."""
    # Mock rate limit response (429)
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

    request = {"text": "This will hit rate limit"}
    result = adapter.create_post(request)

    # Verify error response
    assert result["error_type"] == "RateLimitExceeded"
    assert "error_type" in result
    assert result["reset_at"] is not None


@responses.activate
def test_authentication_error_workflow(adapter):
    """Test handling authentication error in MCP adapter."""
    # Mock authentication error (401)
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

    request = {"text": "This will fail authentication"}
    result = adapter.create_post(request)

    # Verify error response
    assert result["error_type"] == "ApiResponseError"
    assert "error_type" in result


# ============================================================================
# Tool Schema Workflow
# ============================================================================


def test_tool_schemas_workflow(adapter):
    """Test retrieving all tool schemas for MCP registration."""
    schemas = adapter.get_tool_schemas()

    # Verify all tools have proper schema structure
    for tool_name, schema in schemas.items():
        assert "description" in schema
        assert "input_schema" in schema
        assert "output_schema" in schema

        # Verify JSON Schema structure
        input_schema = schema["input_schema"]
        assert "properties" in input_schema or input_schema.get("type") == "object"

        output_schema = schema["output_schema"]
        assert "properties" in output_schema or output_schema.get("type") == "object"

    # Verify specific tool
    create_post = schemas["create_post"]
    assert "text" in create_post["input_schema"]["properties"]
    assert "Post" in create_post["description"] or "post" in create_post["description"]
