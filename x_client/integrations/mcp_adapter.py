"""
MCP (Model Context Protocol) adapter for X API client.

This adapter wraps the PostService and MediaService to provide MCP-compatible
tool interfaces for AI assistants. It handles:
- Schema validation using Pydantic models
- Exception translation to MCP error responses
- Dependency injection for configuration and services
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from x_client.config import ConfigManager, XCredentials
from x_client.exceptions import (
    ApiResponseError,
    AuthenticationError,
    ConfigurationError,
    MediaProcessingFailed,
    MediaProcessingTimeout,
    MediaValidationError,
    RateLimitExceeded,
    XClientError,
)
from x_client.factory import XClientFactory
from x_client.integrations.schema import (
    AuthorResponse,
    DeletePostRequest,
    DeletePostResponse,
    ErrorResponse,
    GetAuthStatusRequest,
    GetAuthStatusResponse,
    GetPostRequest,
    MediaUploadResponse,
    CreatePostRequest,
    CreateThreadRequest,
    CreateThreadResponse,
    RateLimitInfoResponse,
    SearchRecentPostsRequest,
    SearchRecentPostsResponse,
    PostResponse,
    RepostRequest,
    UndoRepostRequest,
    RepostResponse,
    UploadImageRequest,
    UploadVideoRequest,
)
from x_client.services.media_service import MediaService
from x_client.services.post_service import PostService


class XMCPAdapter:
    """
    MCP adapter for X API operations.

    This class provides MCP tool interfaces that wrap the underlying
    PostService and MediaService, handling schema validation and
    error translation.
    """

    def __init__(
        self,
        config: ConfigManager | None = None,
        post_service: PostService | None = None,
        media_service: MediaService | None = None,
    ) -> None:
        """
        Initialize the MCP adapter.

        Args:
            config: Configuration manager (auto-created if not provided)
            post_service: Post service instance (auto-created if not provided)
            media_service: Media service instance (auto-created if not provided)
        """
        self.config = config or ConfigManager()

        # Initialize services if not provided
        if post_service is None or media_service is None:
            client = XClientFactory.create_from_config(self.config)
            self.post_service = post_service or PostService(client)
            self.media_service = media_service or MediaService(client)
        else:
            self.post_service = post_service
            self.media_service = media_service

    # ========================================================================
    # Post Operations
    # ========================================================================

    def create_post(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Post a new post.

        Args:
            request: Request data conforming to CreatePostRequest schema

        Returns:
            Tweet data conforming to PostResponse schema

        Raises:
            ErrorResponse: If the operation fails
        """
        try:
            validated = CreatePostRequest.model_validate(request)

            post = self.post_service.create_post(
                text=validated.text,
                media_ids=validated.media_ids,
                in_reply_to=validated.in_reply_to,
                quote_post_id=validated.quote_post_id,
                reply_settings=validated.reply_settings,
            )

            return self._serialize_post(post).model_dump(exclude_none=True)

        except ValidationError as e:
            return self._convert_validation_error(e)
        except XClientError as e:
            return self._convert_exception(e)

    def create_thread(self, request: dict[str, Any]) -> dict[str, Any]:
        """Create a thread by splitting text into multiple posts."""

        try:
            validated = CreateThreadRequest.model_validate(request)

            result = self.post_service.create_thread(
                text=validated.text,
                chunk_limit=validated.chunk_limit,
                in_reply_to=validated.in_reply_to,
                rollback_on_failure=validated.rollback_on_failure,
            )

            post_responses = [self._serialize_post(post) for post in result.posts]
            error = result.error

            return CreateThreadResponse(
                posts=post_responses,
                succeeded=result.succeeded,
                failed_index=result.failed_index,
                rolled_back=result.rolled_back,
                error=str(error) if error else None,
                error_type=error.__class__.__name__ if error else None,
            ).model_dump(exclude_none=True)

        except ValidationError as e:
            return self._convert_validation_error(e)
        except XClientError as e:
            return self._convert_exception(e)

    def delete_post(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Delete a post.

        Args:
            request: Request data conforming to DeletePostRequest schema

        Returns:
            Deletion result conforming to DeletePostResponse schema

        Raises:
            ErrorResponse: If the operation fails
        """
        try:
            validated = DeletePostRequest.model_validate(request)
            deleted = self.post_service.delete_post(validated.post_id)

            return DeletePostResponse(deleted=deleted).model_dump()

        except ValidationError as e:
            return self._convert_validation_error(e)
        except XClientError as e:
            return self._convert_exception(e)

    def get_post(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Retrieve a specific post.

        Args:
            request: Request data conforming to GetPostRequest schema

        Returns:
            Tweet data conforming to PostResponse schema

        Raises:
            ErrorResponse: If the operation fails
        """
        try:
            validated = GetPostRequest.model_validate(request)
            post = self.post_service.get_post(validated.post_id)
            return self._serialize_post(post).model_dump(exclude_none=True)

        except ValidationError as e:
            return self._convert_validation_error(e)
        except XClientError as e:
            return self._convert_exception(e)

    def search_recent_posts(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Search for recent posts.

        Args:
            request: Request data conforming to SearchRecentPostsRequest schema

        Returns:
            Search results conforming to SearchRecentPostsResponse schema

        Raises:
            ErrorResponse: If the operation fails
        """
        try:
            validated = SearchRecentPostsRequest.model_validate(request)
            posts = self.post_service.search_recent(
                query=validated.query,
                max_results=validated.max_results,
                expansions=validated.expansions,
                post_fields=validated.tweet_fields,
                user_fields=validated.user_fields,
            )

            post_responses = [self._serialize_post(post) for post in posts]

            return SearchRecentPostsResponse(posts=post_responses).model_dump()

        except ValidationError as e:
            return self._convert_validation_error(e)
        except XClientError as e:
            return self._convert_exception(e)

    def repost_post(self, request: dict[str, Any]) -> dict[str, Any]:
        """Repost a post on behalf of the authenticated user."""

        try:
            validated = RepostRequest.model_validate(request)
            result = self.post_service.repost_post(validated.post_id)

            return RepostResponse(reposted=result.reposted).model_dump()

        except ValidationError as e:
            return self._convert_validation_error(e)
        except XClientError as e:
            return self._convert_exception(e)

    def undo_repost(self, request: dict[str, Any]) -> dict[str, Any]:
        """Undo a previously performed repost."""

        try:
            validated = UndoRepostRequest.model_validate(request)
            result = self.post_service.undo_repost(validated.post_id)

            return RepostResponse(reposted=result.reposted).model_dump()

        except ValidationError as e:
            return self._convert_validation_error(e)
        except XClientError as e:
            return self._convert_exception(e)

    # ========================================================================
    # Media Operations
    # ========================================================================

    def upload_image(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Upload an image file.

        Args:
            request: Request data conforming to UploadImageRequest schema

        Returns:
            Upload result conforming to MediaUploadResponse schema

        Raises:
            ErrorResponse: If the operation fails
        """
        try:
            validated = UploadImageRequest.model_validate(request)
            result = self.media_service.upload_image(
                path=Path(validated.path),
                media_category=validated.media_category,
            )

            return self._convert_media_result(result)

        except ValidationError as e:
            return self._convert_validation_error(e)
        except XClientError as e:
            return self._convert_exception(e)

    def upload_video(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Upload a video file.

        Args:
            request: Request data conforming to UploadVideoRequest schema

        Returns:
            Upload result conforming to MediaUploadResponse schema

        Raises:
            ErrorResponse: If the operation fails
        """
        try:
            validated = UploadVideoRequest.model_validate(request)
            result = self.media_service.upload_video(
                path=Path(validated.path),
                media_category=validated.media_category,
                poll_interval=validated.poll_interval,
                timeout=validated.timeout,
            )

            return self._convert_media_result(result)

        except ValidationError as e:
            return self._convert_validation_error(e)
        except XClientError as e:
            return self._convert_exception(e)

    # ========================================================================
    # Authentication & Status
    # ========================================================================

    def get_auth_status(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Get authentication status and rate limit information.

        Args:
            request: Request data conforming to GetAuthStatusRequest schema

        Returns:
            Status data conforming to GetAuthStatusResponse schema

        Raises:
            ErrorResponse: If the operation fails
        """
        try:
            GetAuthStatusRequest.model_validate(request)

            creds: XCredentials | None = None
            # Check if credentials are loaded
            try:
                creds = self.config.load_credentials()
                authenticated = bool(
                    creds.api_key
                    and creds.api_secret
                    and creds.access_token
                    and creds.access_token_secret
                )
            except ConfigurationError:
                authenticated = False

            user_id = self._extract_user_id(creds) if authenticated and creds else None
            rate_limit_info = self._get_rate_limit_info() if authenticated else None

            return GetAuthStatusResponse(
                authenticated=authenticated,
                user_id=user_id,
                rate_limit=rate_limit_info,
            ).model_dump(exclude_none=True)

        except ValidationError as e:
            return self._convert_validation_error(e)
        except XClientError as e:
            return self._convert_exception(e)

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _extract_user_id(self, creds: XCredentials) -> str | None:
        """Extract or derive a stable identifier from the OAuth1 access token."""
        token = creds.access_token
        if not token:
            return None

        if "-" in token:
            candidate = token.split("-", 1)[0]
            if candidate.isdigit():
                return candidate

        # Fall back to a deterministic, anonymised identifier so callers still
        # receive a string without exposing the raw access token.
        digest = sha256(token.encode("utf-8")).hexdigest()[:12]
        return f"token-{digest}"

    def _get_rate_limit_info(self) -> RateLimitInfoResponse | None:
        """Retrieve last known rate limit information from the post service."""
        client = getattr(self.post_service, "client", None)
        if client is None:
            return None

        get_rate_limit_info = getattr(client, "get_rate_limit_info", None)
        if not callable(get_rate_limit_info):
            return None

        info = get_rate_limit_info()
        if not info:
            return None

        limit = getattr(info, "limit", None)
        remaining = getattr(info, "remaining", None)
        reset_at = getattr(info, "reset_at", None)

        if limit is None or remaining is None or reset_at is None:
            return None

        try:
            reset_iso = datetime.fromtimestamp(reset_at, tz=timezone.utc).isoformat()
        except (OSError, OverflowError, ValueError):
            return None

        return RateLimitInfoResponse(
            limit=limit,
            remaining=remaining,
            reset_at=reset_iso,
        )

    def _serialize_post(self, post: Post) -> PostResponse:
        author = None
        if post.author is not None:
            author = AuthorResponse(
                id=post.author.id,
                name=post.author.name,
                username=post.author.username,
            )

        return PostResponse(
            id=post.id,
            text=post.text,
            author_id=post.author_id,
            author=author,
            created_at=post.created_at.isoformat() if post.created_at else None,
        )

    def _convert_media_result(self, result: Any) -> dict[str, Any]:
        """Convert MediaUploadResult to MediaUploadResponse schema."""
        processing_info = None
        if result.processing_info:
            processing_info = {
                "state": result.processing_info.state,
                "check_after_secs": result.processing_info.check_after_secs,
                "progress_percent": result.processing_info.progress_percent,
                "error": (
                    {
                        "code": result.processing_info.error.code,
                        "name": result.processing_info.error.name,
                        "message": result.processing_info.error.message,
                    }
                    if result.processing_info.error
                    else None
                ),
            }

        return MediaUploadResponse(
            media_id=result.media_id,
            media_id_string=result.media_id_string,
            media_key=result.media_key,
            expires_after_secs=result.expires_after_secs,
            processing_info=processing_info,
        ).model_dump(exclude_none=True)

    def _convert_exception(self, exc: XClientError) -> dict[str, Any]:
        """Convert XClientError to ErrorResponse schema."""
        error_type = exc.__class__.__name__

        # Extract additional error details
        code = getattr(exc, "code", None)
        reset_at = getattr(exc, "reset_at", None)

        # Format reset_at as ISO 8601 if present
        if reset_at is not None:
            try:
                reset_at_dt = datetime.fromtimestamp(reset_at)
                reset_at = reset_at_dt.isoformat()
            except (ValueError, OSError):
                reset_at = None

        return ErrorResponse(
            error_type=error_type,
            message=str(exc),
            code=code,
            reset_at=reset_at,
            details=None,
        ).model_dump(exclude_none=True)

    def _convert_validation_error(self, exc: ValidationError) -> dict[str, Any]:
        """Convert Pydantic ValidationError to ErrorResponse schema."""
        error_details = {}
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            error_details[field] = error["msg"]

        return ErrorResponse(
            error_type="ValidationError",
            message=f"Request validation failed: {len(exc.errors())} error(s)",
            code=None,
            reset_at=None,
            details=error_details,
        ).model_dump(exclude_none=True)

    # ========================================================================
    # Tool Registration (for MCP frameworks)
    # ========================================================================

    def get_tool_schemas(self) -> dict[str, dict[str, Any]]:
        """
        Get JSON schemas for all available tools.

        Returns:
            Dictionary mapping tool names to their JSON schema definitions
        """
        return {
            "create_post": {
                "description": "Post a new post with optional media, reply, or quote",
                "input_schema": CreatePostRequest.model_json_schema(),
                "output_schema": PostResponse.model_json_schema(),
            },
            "delete_post": {
                "description": "Delete a post by ID",
                "input_schema": DeletePostRequest.model_json_schema(),
                "output_schema": DeletePostResponse.model_json_schema(),
            },
            "create_thread": {
                "description": "Create a multi-post thread from long text",
                "input_schema": CreateThreadRequest.model_json_schema(),
                "output_schema": CreateThreadResponse.model_json_schema(),
            },
            "repost_post": {
                "description": "Repost a post by ID",
                "input_schema": RepostRequest.model_json_schema(),
                "output_schema": RepostResponse.model_json_schema(),
            },
            "undo_repost": {
                "description": "Undo an existing repost by ID",
                "input_schema": UndoRepostRequest.model_json_schema(),
                "output_schema": RepostResponse.model_json_schema(),
            },
            "get_post": {
                "description": "Retrieve a specific post by ID",
                "input_schema": GetPostRequest.model_json_schema(),
                "output_schema": PostResponse.model_json_schema(),
            },
            "search_recent_posts": {
                "description": "Search for recent posts (past 7 days)",
                "input_schema": SearchRecentPostsRequest.model_json_schema(),
                "output_schema": SearchRecentPostsResponse.model_json_schema(),
            },
            "upload_image": {
                "description": "Upload an image file (max 5MB, JPEG/PNG/WebP/GIF). Please provide an absolute file path.",
                "input_schema": UploadImageRequest.model_json_schema(),
                "output_schema": MediaUploadResponse.model_json_schema(),
            },
            "upload_video": {
                "description": "Upload a video file (max 512MB, MP4 with H.264/AAC). Please provide an absolute file path.",
                "input_schema": UploadVideoRequest.model_json_schema(),
                "output_schema": MediaUploadResponse.model_json_schema(),
            },
            "get_auth_status": {
                "description": "Get authentication status and rate limit information",
                "input_schema": GetAuthStatusRequest.model_json_schema(),
                "output_schema": GetAuthStatusResponse.model_json_schema(),
            },
        }
