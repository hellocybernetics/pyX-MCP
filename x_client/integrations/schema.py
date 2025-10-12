"""
MCP (Model Context Protocol) JSON Schema definitions for X API operations.

This module defines Pydantic models for MCP tool inputs and outputs,
providing type-safe interfaces for AI assistants to interact with the X API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Post Operations
# ============================================================================


class CreatePostRequest(BaseModel):
    """Request schema for posting a post."""

    text: str = Field(..., description="Text content of the post (max 280 characters)")
    media_ids: list[str] | None = Field(
        None,
        description="List of media IDs to attach (max 4)",
        max_length=4,
    )
    in_reply_to: str | None = Field(
        None,
        description="Post ID to reply to",
    )
    quote_post_id: str | None = Field(
        None,
        description="Post ID to quote",
    )
    reply_settings: Literal["everyone", "mentioned_users", "following"] | None = Field(
        None,
        description="Who can reply to this post",
    )


class CreateThreadRequest(BaseModel):
    """Request schema for creating a multi-post thread."""

    text: str = Field(..., description="Full text content that will be split into a thread")
    chunk_limit: int = Field(
        280,
        description="Maximum characters per post segment",
        ge=1,
        le=280,
    )
    in_reply_to: str | None = Field(
        None,
        description="Post ID to reply to with the first segment",
    )
    rollback_on_failure: bool = Field(
        True,
        description="Whether to delete previously created posts if a later segment fails",
    )


class AuthorResponse(BaseModel):
    """Response schema for user summaries."""

    id: str = Field(..., description="User ID")
    name: str | None = Field(None, description="Display name")
    username: str | None = Field(None, description="Handle without @")


class PostResponse(BaseModel):
    """Response schema for post operations."""

    id: str = Field(..., description="Unique post ID")
    text: str | None = Field(None, description="Post text content")
    author_id: str | None = Field(None, description="Author user ID")
    author: AuthorResponse | None = Field(None, description="Author metadata when available")
    created_at: str | None = Field(None, description="Post creation timestamp (ISO 8601)")


class CreateThreadResponse(BaseModel):
    """Response schema for thread creation."""

    posts: list[PostResponse] = Field(..., description="Successfully created thread segments")
    succeeded: bool = Field(..., description="Whether all segments were posted")
    failed_index: int | None = Field(
        None,
        description="Index of the segment that failed (0-based)",
    )
    rolled_back: bool = Field(
        False,
        description="Whether previously created segments were deleted after failure",
    )
    error: str | None = Field(None, description="Error message when the thread failed")
    error_type: str | None = Field(
        None,
        description="Exception type raised during failure",
    )


class DeletePostRequest(BaseModel):
    """Request schema for deleting a post."""

    post_id: str = Field(..., description="ID of the post to delete")


class DeletePostResponse(BaseModel):
    """Response schema for post deletion."""

    deleted: bool = Field(..., description="Whether the post was successfully deleted")


class RepostRequest(BaseModel):
    """Request schema for reposting a post."""

    post_id: str = Field(..., description="ID of the post to repost")


class UndoRepostRequest(BaseModel):
    """Request schema for undoing a repost."""

    post_id: str = Field(..., description="ID of the post to undo repost")


class RepostResponse(BaseModel):
    """Response schema indicating repost state."""

    reposted: bool = Field(..., description="Whether the authenticated user currently reposts the post")


class GetPostRequest(BaseModel):
    """Request schema for retrieving a post."""

    post_id: str = Field(..., description="ID of the post to retrieve")


class SearchRecentPostsRequest(BaseModel):
    """Request schema for searching recent posts."""

    query: str = Field(..., description="Search query using X search syntax")
    max_results: int = Field(
        10,
        description="Maximum number of posts to return",
        ge=10,
        le=100,
    )
    expansions: list[str] | None = Field(
        None,
        description="List of expansions to request (e.g., author_id)",
    )
    tweet_fields: list[str] | None = Field(
        None,
        description="Additional tweet fields to request",
    )
    user_fields: list[str] | None = Field(
        None,
        description="User fields to request when expansions include author",
    )


class SearchRecentPostsResponse(BaseModel):
    """Response schema for post search results."""

    posts: list[PostResponse] = Field(
        ...,
        description="List of posts matching the search query",
    )


# ============================================================================
# Media Operations
# ============================================================================


class UploadImageRequest(BaseModel):
    """Request schema for uploading an image."""

    path: str = Field(..., description="Absolute path to the image file")
    media_category: str = Field(
        "post_image",
        description="Media category (post_image or post_gif)",
    )

    @field_validator("path")
    @classmethod
    def validate_path_exists(cls, v: str) -> str:
        """Validate that the file path exists."""
        path = Path(v)
        if not path.exists():
            raise ValueError(f"File not found: {v}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {v}")
        return v


class UploadVideoRequest(BaseModel):
    """Request schema for uploading a video."""

    path: str = Field(..., description="Absolute path to the video file")
    media_category: str = Field(
        "post_video",
        description="Media category (post_video)",
    )
    poll_interval: float = Field(
        2.0,
        description="Interval in seconds to check processing status",
        gt=0,
    )
    timeout: float = Field(
        60.0,
        description="Maximum time in seconds to wait for processing completion",
        gt=0,
    )

    @field_validator("path")
    @classmethod
    def validate_path_exists(cls, v: str) -> str:
        """Validate that the file path exists."""
        path = Path(v)
        if not path.exists():
            raise ValueError(f"File not found: {v}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {v}")
        return v


class MediaProcessingInfoResponse(BaseModel):
    """Response schema for media processing information."""

    state: str = Field(..., description="Processing state (pending, in_progress, succeeded, failed)")
    check_after_secs: int | None = Field(None, description="Seconds to wait before checking status again")
    progress_percent: int | None = Field(None, description="Processing progress percentage (0-100)")
    error: dict[str, str | int] | None = Field(None, description="Error details if processing failed")


class MediaUploadResponse(BaseModel):
    """Response schema for media upload operations."""

    media_id: str = Field(..., description="Unique media ID")
    media_id_string: str | None = Field(None, description="String representation of media ID")
    media_key: str | None = Field(None, description="Media key for v2 API")
    expires_after_secs: int | None = Field(None, description="Seconds until media expires")
    processing_info: MediaProcessingInfoResponse | None = Field(
        None,
        description="Processing status for video/GIF uploads",
    )


# ============================================================================
# Authentication & Status
# ============================================================================


class RateLimitInfoResponse(BaseModel):
    """Response schema for rate limit information."""

    limit: int = Field(..., description="Total rate limit for this endpoint")
    remaining: int = Field(..., description="Remaining requests in current window")
    reset_at: str = Field(..., description="Time when rate limit resets (ISO 8601)")


class GetAuthStatusRequest(BaseModel):
    """Request schema for authentication status check."""

    pass  # No input parameters required


class GetAuthStatusResponse(BaseModel):
    """Response schema for authentication status."""

    authenticated: bool = Field(..., description="Whether the client is authenticated")
    user_id: str | None = Field(None, description="Authenticated user ID")
    rate_limit: RateLimitInfoResponse | None = Field(
        None,
        description="Rate limit information for the current user",
    )


# ============================================================================
# Error Responses
# ============================================================================


class ErrorResponse(BaseModel):
    """Generic error response schema."""

    error_type: str = Field(..., description="Type of error (e.g., ConfigurationError, RateLimitExceeded)")
    message: str = Field(..., description="Human-readable error message")
    code: int | None = Field(None, description="X API error code if applicable")
    reset_at: str | None = Field(None, description="Rate limit reset time (ISO 8601) for RateLimitExceeded")
    details: dict[str, str] | None = Field(None, description="Additional error details")
