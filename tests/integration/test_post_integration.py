"""Integration tests for end-to-end post workflow."""

from __future__ import annotations

import pytest

from x_client.clients.rate_limited_client import RateLimitedClient
from x_client.clients.tweepy_client import TweepyClient
from x_client.config import XCredentials
from x_client.exceptions import ConfigurationError
from x_client.factory import XClientFactory
from x_client.services.post_service import PostService


class _RecordingV2Client:
    """Stub for tweepy.Client that records interactions."""

    def __init__(self) -> None:
        self.create_calls: list[dict[str, object]] = []
        self.delete_calls: list[str] = []
        self.retweet_calls: list[dict[str, object]] = []
        self.unretweet_calls: list[dict[str, object]] = []

    def create_tweet(self, **kwargs):  # type: ignore[no-untyped-def]
        self.create_calls.append(kwargs)
        post_id = f"thread-{len(self.create_calls)}"
        text = kwargs.get("text")
        return {"id": post_id, "text": text}

    def delete_tweet(self, post_id):  # type: ignore[no-untyped-def]
        self.delete_calls.append(post_id)
        return {"deleted": True}

    def retweet(self, **kwargs):  # type: ignore[no-untyped-def]
        self.retweet_calls.append(kwargs)
        return {"reposted": True, "data": {"reposted": True}}

    def unretweet(self, **kwargs):  # type: ignore[no-untyped-def]
        self.unretweet_calls.append(kwargs)
        return {"reposted": False, "data": {"reposted": False}}


class _RecordingV1API:
    """Stub for tweepy.API; methods unused in these tests."""

    pass


@pytest.fixture
def credentials() -> XCredentials:
    """Provide valid test credentials."""
    return XCredentials(
        api_key="test_api_key",
        api_secret="test_api_secret",
        access_token="test_access_token",
        access_token_secret="test_access_token_secret",
        bearer_token="test_bearer_token",
    )


def test_factory_creates_client_with_both_apis(credentials: XCredentials) -> None:
    """Integration: Factory creates RateLimitedClient wrapping TweepyClient with v2 and v1.1 APIs."""
    client = XClientFactory.create_from_credentials(credentials)

    # By default, factory wraps with RateLimitedClient
    assert isinstance(client, RateLimitedClient)

    # Unwrap to check underlying TweepyClient
    unwrapped = client._client
    assert isinstance(unwrapped, TweepyClient)
    assert hasattr(unwrapped, "_client")  # v2 client
    assert hasattr(unwrapped, "_api")  # v1.1 API
    assert unwrapped._client is not None
    assert unwrapped._api is not None


def test_factory_validates_missing_credentials() -> None:
    """Integration: Factory validates required credentials are present."""
    incomplete_credentials = XCredentials(
        api_key="test_key",
        api_secret=None,  # Missing
        access_token="test_token",
        access_token_secret="test_token_secret",
    )

    with pytest.raises(ConfigurationError, match="API key and secret are required"):
        XClientFactory.create_from_credentials(incomplete_credentials)


def test_service_layer_initialization(credentials: XCredentials) -> None:
    """Integration: Service layer properly initializes with factory client."""
    client = XClientFactory.create_from_credentials(credentials)
    post_service = PostService(client)

    assert post_service.client is client
    assert hasattr(post_service, "create_post")
    assert hasattr(post_service, "delete_post")


def test_client_has_all_required_methods(credentials: XCredentials) -> None:
    """Integration: Client exposes all required methods for services."""
    client = XClientFactory.create_from_credentials(credentials)

    # Post operations (v2)
    assert hasattr(client, "create_post")
    assert hasattr(client, "delete_post")
    assert hasattr(client, "get_post")
    assert hasattr(client, "search_recent_posts")

    # Media operations (v1.1)
    assert hasattr(client, "upload_media")
    assert hasattr(client, "get_media_upload_status")


def test_bearer_token_optional_for_v1_operations(credentials: XCredentials) -> None:
    """Integration: Bearer token not required for v1.1-only operations."""
    credentials_without_bearer = XCredentials(
        api_key="test_key",
        api_secret="test_secret",
        access_token="test_token",
        access_token_secret="test_token_secret",
        bearer_token=None,  # Optional
    )

    client = XClientFactory.create_from_credentials(credentials_without_bearer)

    # Should create client successfully
    assert client is not None
    assert hasattr(client, "upload_media")  # v1.1 operations still work


def test_create_thread_via_factory_uses_reply_chain(
    monkeypatch: pytest.MonkeyPatch,
    credentials: XCredentials,
) -> None:
    """Integration: create_thread issues sequential replies via Tweepy client wrappers."""

    created_clients: list[_RecordingV2Client] = []

    def fake_client_ctor(*_args, **_kwargs):
        client = _RecordingV2Client()
        created_clients.append(client)
        return client

    monkeypatch.setattr("x_client.factory.tweepy.Client", fake_client_ctor)
    monkeypatch.setattr("x_client.factory.tweepy.OAuth1UserHandler", lambda *a, **k: object())
    monkeypatch.setattr("x_client.factory.tweepy.API", lambda _auth: _RecordingV1API())

    client = XClientFactory.create_from_credentials(credentials, enable_rate_limiting=False)
    assert isinstance(client, TweepyClient)

    service = PostService(client)
    result = service.create_thread("thread body " * 5, chunk_limit=15)

    assert result.succeeded is True
    assert len(result.posts) >= 2  # 長文なので複数セグメントになる

    fake_client = created_clients[0]
    assert len(fake_client.create_calls) == len(result.posts)

    # 最初の投稿は reply 指定なし、その後は直前の ID に返信する
    for index, kwargs in enumerate(fake_client.create_calls):
        if index == 0:
            assert "in_reply_to_tweet_id" not in kwargs
            continue
        expected_anchor = result.posts[index - 1].id
        assert kwargs["in_reply_to_tweet_id"] == expected_anchor


def test_repost_and_undo_flow_via_factory(
    monkeypatch: pytest.MonkeyPatch,
    credentials: XCredentials,
) -> None:
    """Integration: repost/undo_repost calls tweepy client with user_auth flag."""

    created_clients: list[_RecordingV2Client] = []

    def fake_client_ctor(*_args, **_kwargs):
        client = _RecordingV2Client()
        created_clients.append(client)
        return client

    monkeypatch.setattr("x_client.factory.tweepy.Client", fake_client_ctor)
    monkeypatch.setattr("x_client.factory.tweepy.OAuth1UserHandler", lambda *a, **k: object())
    monkeypatch.setattr("x_client.factory.tweepy.API", lambda _auth: _RecordingV1API())

    client = XClientFactory.create_from_credentials(credentials, enable_rate_limiting=False)
    assert isinstance(client, TweepyClient)
    service = PostService(client)

    repost_result = service.repost_post("555")
    assert repost_result.reposted is True

    undo_result = service.undo_repost("555")
    assert undo_result.reposted is False

    fake_client = created_clients[0]
    assert fake_client.retweet_calls == [{"tweet_id": "555", "user_auth": True}]
    assert fake_client.unretweet_calls == [{"tweet_id": "555", "user_auth": True}]
