from __future__ import annotations

from types import SimpleNamespace
import io

import pytest
import tweepy

from x_client.clients.tweepy_client import TweepyClient, TooManyRequests
from x_client.exceptions import ApiResponseError, RateLimitExceeded


class StubV2Client:
    """Stub for tweepy.Client (v2 API) - tweet operations."""
    def __init__(self, *, create_result=None, tweet=None, search=None) -> None:
        self.create_result = create_result
        self.post = tweet or {"id": "99", "text": "hello"}
        self.search = search or [{"id": "1", "text": "a"}]
        self.called_with: dict[str, tuple[tuple, dict]] = {}
        self._exception: Exception | None = None

    def set_exception(self, exc: Exception) -> None:
        self._exception = exc

    def create_tweet(self, **kwargs):
        self.called_with["create_tweet"] = ((), kwargs)
        if self._exception:
            raise self._exception
        return self.create_result or {"data": {"id": "1"}}

    def delete_tweet(self, post_id):
        self.called_with["delete_tweet"] = ((post_id,), {})
        if self._exception:
            raise self._exception
        return {"status": "ok"}

    def get_tweet(self, post_id, **kwargs):
        self.called_with["get_tweet"] = ((post_id,), kwargs)
        if self._exception:
            raise self._exception
        return self.tweet

    def search_recent_tweets(self, query, **kwargs):
        self.called_with["search_recent_tweets"] = ((query,), kwargs)
        if self._exception:
            raise self._exception
        return SimpleNamespace(data=self.search)


class StubV1API:
    """Stub for tweepy.API (v1.1 API) - media operations."""
    def __init__(self, *, status=None) -> None:
        self.status = status or {"media_id": "123", "processing_info": {"state": "succeeded"}}
        self.called_with: dict[str, tuple[tuple, dict]] = {}
        self._exception: Exception | None = None

    def set_exception(self, exc: Exception) -> None:
        self._exception = exc

    def media_upload(self, *, filename, file=None, media_category=None, chunked=False, **kwargs):
        self.called_with["media_upload"] = (
            (filename,),
            {"file": file, "media_category": media_category, "chunked": chunked, **kwargs},
        )
        if self._exception:
            raise self._exception
        return self.status

    def get_media_upload_status(self, media_id):
        self.called_with["get_media_upload_status"] = ((media_id,), {})
        if self._exception:
            raise self._exception
        return self.status


def test_create_post_delegates_and_returns_response() -> None:
    v2_client = StubV2Client(create_result={"data": {"id": "42"}})
    v1_api = StubV1API()
    client = TweepyClient(v2_client, v1_api)  # type: ignore[arg-type]

    response = client.create_post(text="hello world")

    assert response["data"]["id"] == "42"
    assert v2_client.called_with["create_tweet"][1]["text"] == "hello world"


def test_delete_post_translates_exceptions() -> None:
    v2_client = StubV2Client()
    v1_api = StubV1API()

    class TweepyError(tweepy.errors.TweepyException):
        def __init__(self):
            super().__init__("boom")
            self.api_codes = [1234]

    v2_client.set_exception(TweepyError())
    client = TweepyClient(v2_client, v1_api)  # type: ignore[arg-type]

    with pytest.raises(ApiResponseError) as exc:
        client.delete_post("tweet-id")

    assert exc.value.code == 1234


def test_rate_limit_errors_translate_to_domain_exception() -> None:
    v2_client = StubV2Client()
    v1_api = StubV1API()

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

    v2_client.set_exception(RateLimitError())
    client = TweepyClient(v2_client, v1_api)  # type: ignore[arg-type]

    with pytest.raises(RateLimitExceeded) as exc:
        client.create_post(text="hello")

    assert exc.value.reset_at == 1700000000


def test_get_post_delegates_to_underlying_client() -> None:
    v2_client = StubV2Client(tweet={"id": "55", "text": "fizz"})
    v1_api = StubV1API()
    client = TweepyClient(v2_client, v1_api)  # type: ignore[arg-type]

    response = client.get_post("55", expansions="author_id")

    assert response["id"] == "55"
    assert v2_client.called_with["get_tweet"][0][0] == "55"
    assert v2_client.called_with["get_tweet"][1]["expansions"] == "author_id"


def test_search_recent_tweets_delegates() -> None:
    v2_client = StubV2Client(search=[{"id": "10", "text": "term"}])
    v1_api = StubV1API()
    client = TweepyClient(v2_client, v1_api)  # type: ignore[arg-type]

    response = client.search_recent_posts("query", max_results=5)

    assert isinstance(response.data, list)
    assert v2_client.called_with["search_recent_tweets"][0][0] == "query"
    assert v2_client.called_with["search_recent_tweets"][1]["max_results"] == 5


def test_upload_media_omits_media_type_for_non_chunked() -> None:
    v2_client = StubV2Client()
    v1_api = StubV1API()
    client = TweepyClient(v2_client, v1_api)  # type: ignore[arg-type]

    file_obj = io.BytesIO(b"pngdata")
    file_obj.name = "image.png"  # type: ignore[attr-defined]

    client.upload_media(file=file_obj, media_category="post_image", mime_type="image/png", chunked=False)

    kwargs = v1_api.called_with["media_upload"][1]
    assert kwargs["media_category"] == "post_image"
    assert kwargs["chunked"] is False
    assert kwargs["file"] is None


def test_upload_media_strips_media_type_when_chunked() -> None:
    v2_client = StubV2Client()
    v1_api = StubV1API()
    client = TweepyClient(v2_client, v1_api)  # type: ignore[arg-type]

    file_obj = io.BytesIO(b"videodata")
    file_obj.name = "video.mp4"  # type: ignore[attr-defined]

    client.upload_media(file=file_obj, media_category="post_video", mime_type="video/mp4", chunked=True)

    kwargs = v1_api.called_with["media_upload"][1]
    assert kwargs["media_category"] == "post_video"
    assert kwargs["chunked"] is True
    assert kwargs["file"] is file_obj
