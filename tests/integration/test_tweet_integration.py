"""Integration tests for end-to-end tweet workflow."""

from __future__ import annotations

import pytest

from twitter_client.clients.tweepy_client import TweepyClient
from twitter_client.config import TwitterCredentials
from twitter_client.exceptions import ConfigurationError
from twitter_client.factory import TwitterClientFactory
from twitter_client.services.tweet_service import TweetService


@pytest.fixture
def credentials() -> TwitterCredentials:
    """Provide valid test credentials."""
    return TwitterCredentials(
        api_key="test_api_key",
        api_secret="test_api_secret",
        access_token="test_access_token",
        access_token_secret="test_access_token_secret",
        bearer_token="test_bearer_token",
    )


def test_factory_creates_client_with_both_apis(credentials: TwitterCredentials) -> None:
    """Integration: Factory creates TweepyClient with v2 and v1.1 APIs."""
    client = TwitterClientFactory.create_from_credentials(credentials)

    assert isinstance(client, TweepyClient)
    assert hasattr(client, "_client")  # v2 client
    assert hasattr(client, "_api")  # v1.1 API
    assert client._client is not None
    assert client._api is not None


def test_factory_validates_missing_credentials() -> None:
    """Integration: Factory validates required credentials are present."""
    incomplete_credentials = TwitterCredentials(
        api_key="test_key",
        api_secret=None,  # Missing
        access_token="test_token",
        access_token_secret="test_token_secret",
    )

    with pytest.raises(ConfigurationError, match="API key and secret are required"):
        TwitterClientFactory.create_from_credentials(incomplete_credentials)


def test_service_layer_initialization(credentials: TwitterCredentials) -> None:
    """Integration: Service layer properly initializes with factory client."""
    client = TwitterClientFactory.create_from_credentials(credentials)
    tweet_service = TweetService(client)

    assert tweet_service.client is client
    assert hasattr(tweet_service, "create_tweet")
    assert hasattr(tweet_service, "delete_tweet")


def test_client_has_all_required_methods(credentials: TwitterCredentials) -> None:
    """Integration: Client exposes all required methods for services."""
    client = TwitterClientFactory.create_from_credentials(credentials)

    # Tweet operations (v2)
    assert hasattr(client, "create_tweet")
    assert hasattr(client, "delete_tweet")
    assert hasattr(client, "get_tweet")
    assert hasattr(client, "search_recent_tweets")

    # Media operations (v1.1)
    assert hasattr(client, "upload_media")
    assert hasattr(client, "get_media_upload_status")


def test_bearer_token_optional_for_v1_operations(credentials: TwitterCredentials) -> None:
    """Integration: Bearer token not required for v1.1-only operations."""
    credentials_without_bearer = TwitterCredentials(
        api_key="test_key",
        api_secret="test_secret",
        access_token="test_token",
        access_token_secret="test_token_secret",
        bearer_token=None,  # Optional
    )

    client = TwitterClientFactory.create_from_credentials(credentials_without_bearer)

    # Should create client successfully
    assert client is not None
    assert hasattr(client, "upload_media")  # v1.1 operations still work
