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
            data=[{"id": "333", "text": "search result", "author_id": "user1"}],
            includes={
                "users": [
                    {"id": "user1", "name": "User One", "username": "userone"}
                ]
            },
        )
        self.create_call_count = 0
        self.fail_on_calls: set[int] = set()
        self.create_history: list[dict[str, object]] = []
        self.repost_response: dict[str, object] = {"reposted": True}
        self.undo_repost_response: dict[str, object] = {"reposted": False}
        self.repost_ids: list[str] = []
        self.undo_repost_ids: list[str] = []

    def create_post(self, **kwargs):
        self.create_call_count += 1
        if self.create_call_count in self.fail_on_calls:
            raise ApiResponseError("failed")

        self.create_kwargs = kwargs
        self.create_history.append(kwargs)
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

    def repost_post(self, post_id):
        self.repost_ids.append(post_id)
        return self.repost_response

    def undo_repost(self, post_id):
        self.undo_repost_ids.append(post_id)
        return self.undo_repost_response


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
    assert client.create_kwargs["in_reply_to_tweet_id"] == "99"
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


def test_search_recent_with_expansions_and_author() -> None:
    client = FakePostClient()
    service = PostService(client)

    posts = service.search_recent(
        "query",
        max_results=25,
        expansions=["author_id"],
        post_fields=["created_at"],
        user_fields=["username"],
    )

    assert client.search_kwargs == {
        "query": "query",
        "max_results": 25,
        "expansions": ["author_id"],
        "tweet_fields": ["created_at"],
        "user_fields": ["username"],
    }

    assert len(posts) == 1
    post = posts[0]
    assert post.author is not None
    assert post.author.username == "userone"


def test_create_thread_success_builds_chain() -> None:
    client = FakePostClient()
    service = PostService(client)

    result = service.create_thread("hello world " * 20, chunk_limit=30)

    assert result.succeeded is True
    assert len(result.posts) > 1
    assert client.create_call_count == len(result.posts)

    # Ensure subsequent posts reply to prior ID
    for index, kwargs in enumerate(client.create_history):
        if index == 0:
            assert "in_reply_to_tweet_id" not in kwargs
        else:
            assert (
                kwargs["in_reply_to_tweet_id"]
                == result.posts[index - 1].id
            )


def test_create_thread_applies_segment_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakePostClient()
    service = PostService(client)

    sleeps: list[float] = []

    def fake_sleep(duration: float) -> None:
        sleeps.append(duration)

    monkeypatch.setattr("x_client.services.post_service.time.sleep", fake_sleep)

    result = service.create_thread(
        "segment one segment two segment three segment four",
        chunk_limit=15,
        segment_pause=0.5,
    )

    assert result.succeeded is True
    # Expect sleep to run between each segment except the last
    expected_sleeps = max(0, len(client.create_history) - 1)
    assert len(sleeps) == expected_sleeps
    assert all(duration == 0.5 for duration in sleeps)


def test_create_thread_rolls_back_on_failure() -> None:
    client = FakePostClient()
    client.fail_on_calls = {2}
    service = PostService(client)

    result = service.create_thread(["first", "second", "third"], chunk_limit=280)

    assert result.succeeded is False
    assert result.failed_index == 1
    assert result.error is not None
    # First post created and then deleted due to rollback
    assert client.delete_ids == [result.posts[0].id]


def test_repost_post_success() -> None:
    client = FakePostClient()
    service = PostService(client)

    result = service.repost_post("999")

    assert result.reposted is True
    assert client.repost_ids == ["999"]


def test_undo_repost_success() -> None:
    client = FakePostClient()
    service = PostService(client)

    result = service.undo_repost("999")

    assert result.reposted is False
    assert client.undo_repost_ids == ["999"]


def test_repost_post_failure_raises() -> None:
    client = FakePostClient()
    client.repost_response = {"reposted": False}
    service = PostService(client)

    with pytest.raises(ApiResponseError):
        service.repost_post("999")


def test_undo_repost_failure_raises() -> None:
    client = FakePostClient()
    client.undo_repost_response = {"reposted": True}
    service = PostService(client)

    with pytest.raises(ApiResponseError):
        service.undo_repost("999")


def test_create_post_emits_events() -> None:
    client = FakePostClient()
    events: list[tuple[str, dict[str, object]]] = []

    def hook(name: str, payload: dict[str, object]) -> None:
        events.append((name, payload))

    service = PostService(client, event_hook=hook)
    post = service.create_post("observable text")

    assert post.id == "111"
    assert [name for name, _ in events] == [
        "post.create.start",
        "post.create.success",
    ]


def test_create_post_failure_emits_error_event() -> None:
    client = FakePostClient()
    client.fail_on_calls = {1}
    events: list[tuple[str, dict[str, object]]] = []

    service = PostService(client, event_hook=lambda name, payload: events.append((name, payload)))

    with pytest.raises(ApiResponseError):
        service.create_post("should fail")

    assert [name for name, _ in events][-1] == "post.create.error"


def test_create_thread_emits_segment_events() -> None:
    client = FakePostClient()
    events: list[str] = []

    service = PostService(client, event_hook=lambda name, payload: events.append(name))

    result = service.create_thread("segment " * 10, chunk_limit=10)

    assert result.succeeded is True
    assert events[0] == "post.thread.start"
    assert "post.thread.success" in events
    segment_events = [name for name in events if name == "post.thread.segment_success"]
    assert len(segment_events) == len(result.posts)
