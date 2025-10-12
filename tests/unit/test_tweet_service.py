from __future__ import annotations

from types import SimpleNamespace

import pytest

from twitter_client.exceptions import ApiResponseError
from twitter_client.services.tweet_service import TweetService


class FakeTweetClient:
    def __init__(self) -> None:
        self.create_kwargs: dict[str, object] | None = None
        self.delete_ids: list[str] = []
        self.get_kwargs: tuple[str, dict] | None = None
        self.search_kwargs: dict[str, object] | None = None
        self.create_response: dict[str, object] = {"id": "111", "text": "hello"}
        self.delete_response: dict[str, object] = {"deleted": True}
        self.tweet_response: dict[str, object] = {"id": "222", "text": "hi"}
        self.search_response: SimpleNamespace = SimpleNamespace(
            data=[{"id": "333", "text": "search result"}]
        )

    def create_tweet(self, **kwargs):
        self.create_kwargs = kwargs
        return self.create_response

    def delete_tweet(self, tweet_id):
        self.delete_ids.append(tweet_id)
        return self.delete_response

    def get_tweet(self, tweet_id, **kwargs):
        self.get_kwargs = (tweet_id, kwargs)
        return self.tweet_response

    def search_recent_tweets(self, query, **kwargs):
        self.search_kwargs = {"query": query, **kwargs}
        return self.search_response


def test_create_tweet_builds_payload() -> None:
    client = FakeTweetClient()
    service = TweetService(client)

    tweet = service.create_tweet(
        "hello",
        media_ids=["1", "2"],
        in_reply_to="99",
        quote_tweet_id="77",
        reply_settings="followers",
    )

    assert tweet.id == "111"
    assert client.create_kwargs is not None
    assert client.create_kwargs["media_ids"] == [1, 2]
    assert client.create_kwargs["user_auth"] is True
    assert client.create_kwargs["reply"] == {"in_reply_to_tweet_id": "99"}
    assert client.create_kwargs["quote_tweet_id"] == "77"
    assert client.create_kwargs["reply_settings"] == "followers"


def test_delete_tweet_raises_when_not_deleted() -> None:
    client = FakeTweetClient()
    client.delete_response = {"deleted": False}
    service = TweetService(client)

    with pytest.raises(ApiResponseError):
        service.delete_tweet("abc")


def test_get_tweet_returns_model() -> None:
    client = FakeTweetClient()
    client.tweet_response = {"id": "444", "text": "body"}
    service = TweetService(client)

    tweet = service.get_tweet("444", expansions="author_id")

    assert tweet.id == "444"
    assert client.get_kwargs == ("444", {"expansions": "author_id"})


def test_search_recent_handles_empty_result() -> None:
    client = FakeTweetClient()
    client.search_response = SimpleNamespace(data=None)
    service = TweetService(client)

    tweets = service.search_recent("query")

    assert tweets == []
