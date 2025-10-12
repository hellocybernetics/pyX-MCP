"""
Post related workflows built on top of client adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Protocol

from x_client.exceptions import ApiResponseError
from x_client.models import Post, PostDeleteResult


class PostClient(Protocol):
    """Protocol subset consumed by the service."""

    def create_post(self, **kwargs: Any) -> Any:
        ...

    def delete_post(self, post_id: str) -> Any:
        ...

    def get_post(self, *args: Any, **kwargs: Any) -> Any:
        ...

    def search_recent_posts(self, *args: Any, **kwargs: Any) -> Any:
        ...


@dataclass(slots=True)
class PostService:
    """High level orchestration for post CRUD operations."""

    client: PostClient

    def create_post(
        self,
        text: str,
        *,
        media_ids: Iterable[str] | None = None,
        in_reply_to: str | None = None,
        quote_post_id: str | None = None,
        reply_settings: str | None = None,
        **extra: Any,
    ) -> Post:
        payload: dict[str, Any] = {"text": text}
        if media_ids:
            payload["media_ids"] = [int(media_id) for media_id in media_ids]
            payload["user_auth"] = True
        if in_reply_to:
            payload["reply"] = {"in_reply_to_post_id": in_reply_to}
        if quote_post_id:
            payload["quote_post_id"] = quote_post_id
        if reply_settings:
            payload["reply_settings"] = reply_settings
        payload.update(extra)
        response = self.client.create_post(**payload)
        return Post.from_api(response)

    def delete_post(self, post_id: str) -> bool:
        response = self.client.delete_post(post_id)
        result = PostDeleteResult.from_api(response)
        if not result.deleted:
            raise ApiResponseError(f"Unable to delete post '{post_id}'.")
        return True

    def get_post(self, post_id: str, **kwargs: Any) -> Post:
        response = self.client.get_post(post_id, **kwargs)
        return Post.from_api(response)

    def search_recent(self, query: str, **kwargs: Any) -> list[Post]:
        response = self.client.search_recent_posts(query, **kwargs)
        data = getattr(response, "data", response)
        if not data:
            return []

        if isinstance(data, list):
            return [Post.from_api(item) for item in data]

        # When tweepy returns a single Post instance rather than list
        return [Post.from_api(data)]
