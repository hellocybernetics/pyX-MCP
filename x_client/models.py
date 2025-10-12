"""
Pydantic models for X (Twitter) API responses used by x_client.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, field_validator


def _to_mapping(payload: Any) -> Mapping[str, Any]:
    if isinstance(payload, Mapping):
        return payload
    if hasattr(payload, "data"):
        return _to_mapping(payload.data)
    if hasattr(payload, "__dict__"):
        return _to_mapping(vars(payload))
    raise TypeError(f"Cannot convert payload of type {type(payload)!r} to mapping.")


class Post(BaseModel):
    """Normalized representation of a post."""

    id: str
    text: str | None = None
    author_id: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(extra="allow")

    @classmethod
    def from_api(cls, payload: Any) -> "Post":
        return cls.model_validate(_to_mapping(payload))


class PostDeleteResult(BaseModel):
    """Represents the outcome of a delete post call."""

    deleted: bool

    @classmethod
    def from_api(cls, payload: Any) -> "PostDeleteResult":
        return cls.model_validate(_to_mapping(payload))


class MediaProcessingError(BaseModel):
    code: int | None = None
    name: str | None = None
    message: str | None = None


class MediaProcessingInfo(BaseModel):
    state: str
    check_after_secs: int | None = None
    progress_percent: int | None = None
    error: MediaProcessingError | None = None

    model_config = ConfigDict(extra="allow")


class MediaUploadResult(BaseModel):
    """Normalized response from the media upload endpoints."""

    media_id: str
    media_id_string: str | None = None
    media_key: str | None = None
    expires_after_secs: int | None = None
    processing_info: MediaProcessingInfo | None = None

    model_config = ConfigDict(extra="allow")

    @classmethod
    def from_api(cls, payload: Any) -> "MediaUploadResult":
        return cls.model_validate(_to_mapping(payload))

    @field_validator("media_id", mode="before")
    @classmethod
    def coerce_media_id(cls, value: Any) -> str:
        if isinstance(value, (int, float)):
            return str(int(value))
        if isinstance(value, str):
            return value
        raise TypeError("media_id must be serializable to str.")
