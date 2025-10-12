"""
Pydantic models for X (Twitter) API responses used by x_client.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, field_validator


class User(BaseModel):
    """Normalized representation of a user."""

    id: str
    name: str | None = None
    username: str | None = None

    model_config = ConfigDict(extra="allow")

    @classmethod
    def from_api(cls, payload: Any) -> "User":
        return cls.model_validate(_to_mapping(payload))


def _to_mapping(payload: Any) -> Mapping[str, Any]:
    if isinstance(payload, Mapping):
        return payload
    if hasattr(payload, "data"):
        return _to_mapping(payload.data)
    if hasattr(payload, "__dict__"):
        return _to_mapping(vars(payload))
    raise TypeError(f"Cannot convert payload of type {type(payload)!r} to mapping.")


def _lookup_author(author_id: str, includes: Mapping[str, Any]) -> Any | None:
    users: Any | None = None
    if isinstance(includes, Mapping):
        users = includes.get("users")
    else:
        users = getattr(includes, "users", None)

    if users is None:
        return None

    if isinstance(users, Mapping):
        candidate = users.get(author_id)
        if candidate is not None:
            return candidate

    if isinstance(users, Sequence):
        for entry in users:
            try:
                entry_mapping = _to_mapping(entry)
            except TypeError:
                continue
            if entry_mapping.get("id") == author_id:
                return entry_mapping

    return None


class Post(BaseModel):
    """Normalized representation of a post."""

    id: str
    text: str | None = None
    author_id: str | None = None
    author: User | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(extra="allow")

    @classmethod
    def from_api(
        cls,
        payload: Any,
        *,
        includes: Mapping[str, Any] | None = None,
    ) -> "Post":
        mapping = dict(_to_mapping(payload))

        author_id = mapping.get("author_id")
        if author_id and includes:
            author_payload = _lookup_author(author_id, includes)
            if author_payload:
                mapping["author"] = User.from_api(author_payload)

        return cls.model_validate(mapping)


class PostDeleteResult(BaseModel):
    """Represents the outcome of a delete post call."""

    deleted: bool

    @classmethod
    def from_api(cls, payload: Any) -> "PostDeleteResult":
        return cls.model_validate(_to_mapping(payload))


class RepostResult(BaseModel):
    """Represents the outcome of repost/undo repost operations."""

    reposted: bool

    model_config = ConfigDict(extra="allow")

    @classmethod
    def from_api(cls, payload: Any) -> "RepostResult":
        mapping = _to_mapping(payload)
        if "reposted" in mapping:
            value = mapping["reposted"]
        elif "retweeted" in mapping:
            value = mapping["retweeted"]
        else:
            value = mapping.get("data", {}).get("reposted") or mapping.get("data", {}).get(
                "retweeted"
            )

        if value is None:
            raise TypeError("Cannot determine repost state from payload.")

        return cls.model_validate({"reposted": bool(value)})


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
