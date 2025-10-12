"""Integration tests for end-to-end post workflow."""

from __future__ import annotations

import pytest

from x_client.clients.rate_limited_client import RateLimitedClient
from x_client.clients.tweepy_client import TweepyClient
from x_client.config import XCredentials
from x_client.exceptions import ConfigurationError
from x_client.factory import XClientFactory
from x_client.services.post_service import PostService


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
