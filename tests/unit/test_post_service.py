from __future__ import annotations

from types import SimpleNamespace

import pytest

from x_client.exceptions import ApiResponseError
from x_client.services.post_service import PostService


class FakePostClient:
    def __init__(self) -> None:
        self.create_kwargs: dict[str, object] | None = None
        self.delete_ids: list[str] = []
        self.get_kwargs: tuple[str, dict] | None = None
        self.search_kwargs: dict[str, object] | None = None
        self.create_response: dict[str, object] = {"id": "111", "text": "hello"}
        self.delete_response: dict[str, object] = {"deleted": True}
        self.post_response: dict[str, object] = {"id": "222", "text": "hi"}
        self.search_response: SimpleNamespace = SimpleNamespace(
            data=[{"id": "333", "text": "search result"}]
        )

    def create_post(self, **kwargs):
        self.create_kwargs = kwargs
        return self.create_response

    def delete_post(self, post_id):
        self.delete_ids.append(post_id)
        return self.delete_response

    def get_post(self, post_id, **kwargs):
        self.get_kwargs = (post_id, kwargs)
        return self.post_response

    def search_recent_posts(self, query, **kwargs):
        self.search_kwargs = {"query": query, **kwargs}
        return self.search_response


def test_create_post_builds_payload() -> None:
    client = FakePostClient()
    service = PostService(client)

    post = service.create_post(
        "hello",
        media_ids=["1", "2"],
        in_reply_to="99",
        quote_post_id="77",
        reply_settings="followers",
    )

    assert post.id == "111"
    assert client.create_kwargs is not None
    assert client.create_kwargs["media_ids"] == [1, 2]
    assert client.create_kwargs["user_auth"] is True
    assert client.create_kwargs["reply"] == {"in_reply_to_post_id": "99"}
    assert client.create_kwargs["quote_post_id"] == "77"
    assert client.create_kwargs["reply_settings"] == "followers"


def test_delete_post_raises_when_not_deleted() -> None:
    client = FakePostClient()
    client.delete_response = {"deleted": False}
    service = PostService(client)

    with pytest.raises(ApiResponseError):
        service.delete_post("abc")


def test_get_post_returns_model() -> None:
    client = FakePostClient()
    client.post_response = {"id": "444", "text": "body"}
    service = PostService(client)

    post = service.get_post("444", expansions="author_id")

    assert post.id == "444"
    assert client.get_kwargs == ("444", {"expansions": "author_id"})


def test_search_recent_handles_empty_result() -> None:
    client = FakePostClient()
    client.search_response = SimpleNamespace(data=None)
    service = PostService(client)

    posts = service.search_recent("query")

    assert posts == []
