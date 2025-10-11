from __future__ import annotations

from types import SimpleNamespace

import pytest
import tweepy

from twitter_client.clients.tweepy_client import TweepyClient, TooManyRequests
from twitter_client.exceptions import ApiResponseError, RateLimitExceeded


class StubTweepyClient:
    def __init__(self, *, create_result=None, tweet=None, search=None, status=None) -> None:
        self.create_result = create_result
        self.tweet = tweet or {"id": "99", "text": "hello"}
        self.search = search or [{"id": "1", "text": "a"}]
        self.status = status or {"media_id": "123", "processing_info": {"state": "succeeded"}}
        self.called_with: dict[str, tuple[tuple, dict]] = {}
        self._exception: Exception | None = None

    def set_exception(self, exc: Exception) -> None:
        self._exception = exc

    def create_tweet(self, **kwargs):
        self.called_with["create_tweet"] = ((), kwargs)
        if self._exception:
            raise self._exception
        return self.create_result or {"data": {"id": "1"}}

    def delete_tweet(self, tweet_id):
        self.called_with["delete_tweet"] = ((tweet_id,), {})
        if self._exception:
            raise self._exception
        return {"status": "ok"}

    def get_tweet(self, tweet_id, **kwargs):
        self.called_with["get_tweet"] = ((tweet_id,), kwargs)
        if self._exception:
            raise self._exception
        return self.tweet

    def search_recent_tweets(self, query, **kwargs):
        self.called_with["search_recent_tweets"] = ((query,), kwargs)
        if self._exception:
            raise self._exception
        return SimpleNamespace(data=self.search)

    def upload_media(self, *, file, media_category, mime_type=None, **kwargs):
        self.called_with["upload_media"] = ((file,), {"media_category": media_category, "mime_type": mime_type, **kwargs})
        if self._exception:
            raise self._exception
        return self.status

    def get_media_upload_status(self, media_id):
        self.called_with["get_media_upload_status"] = ((media_id,), {})
        if self._exception:
            raise self._exception
        return self.status


def test_create_tweet_delegates_and_returns_response() -> None:
    inner = StubTweepyClient(create_result={"data": {"id": "42"}})
    client = TweepyClient(inner)  # type: ignore[arg-type]

    response = client.create_tweet(text="hello world")

    assert response["data"]["id"] == "42"
    assert inner.called_with["create_tweet"][1]["text"] == "hello world"


def test_delete_tweet_translates_exceptions() -> None:
    inner = StubTweepyClient()

    class TweepyError(tweepy.errors.TweepyException):
        def __init__(self):
            super().__init__("boom")
            self.api_codes = [1234]

    inner.set_exception(TweepyError())
    client = TweepyClient(inner)  # type: ignore[arg-type]

    with pytest.raises(ApiResponseError) as exc:
        client.delete_tweet("tweet-id")

    assert exc.value.code == 1234


def test_rate_limit_errors_translate_to_domain_exception() -> None:
    inner = StubTweepyClient()

    class RateLimitError(TooManyRequests):  # type: ignore[misc]
        def __init__(self):
            response = SimpleNamespace(
                status_code=429,
                status=429,
                headers={"x-rate-limit-reset": "1700000000"},
                json=lambda: {},
                reason="Too Many Requests",
            )
            super().__init__(response)
            self.response = response

    inner.set_exception(RateLimitError())
    client = TweepyClient(inner)  # type: ignore[arg-type]

    with pytest.raises(RateLimitExceeded) as exc:
        client.create_tweet(text="hello")

    assert exc.value.reset_at == 1700000000


def test_get_tweet_delegates_to_underlying_client() -> None:
    inner = StubTweepyClient(tweet={"id": "55", "text": "fizz"})
    client = TweepyClient(inner)  # type: ignore[arg-type]

    response = client.get_tweet("55", expansions="author_id")

    assert response["id"] == "55"
    assert inner.called_with["get_tweet"][0][0] == "55"
    assert inner.called_with["get_tweet"][1]["expansions"] == "author_id"


def test_search_recent_tweets_delegates() -> None:
    inner = StubTweepyClient(search=[{"id": "10", "text": "term"}])
    client = TweepyClient(inner)  # type: ignore[arg-type]

    response = client.search_recent_tweets("query", max_results=5)

    assert isinstance(response.data, list)
    assert inner.called_with["search_recent_tweets"][0][0] == "query"
    assert inner.called_with["search_recent_tweets"][1]["max_results"] == 5
