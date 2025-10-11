from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from twitter_client.config import ConfigManager, TwitterCredentials
from twitter_client.exceptions import ConfigurationError
from twitter_client.factory import TwitterClientFactory


def test_create_from_config_initializes_dual_client() -> None:
    """Factory creates TweepyClient with both v2 and v1.1 instances."""
    config = Mock(spec=ConfigManager)
    config.load_credentials.return_value = TwitterCredentials(
        api_key="test_key",
        api_secret="test_secret",
        access_token="test_token",
        access_token_secret="test_token_secret",
        bearer_token="test_bearer",
    )

    with patch("twitter_client.factory.tweepy") as mock_tweepy:
        mock_v2_client = Mock()
        mock_v1_api = Mock()
        mock_tweepy.Client.return_value = mock_v2_client
        mock_tweepy.API.return_value = mock_v1_api

        client = TwitterClientFactory.create_from_config(config)

        # Verify v2 client initialization
        mock_tweepy.Client.assert_called_once_with(
            bearer_token="test_bearer",
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
        )

        # Verify v1 API initialization
        mock_tweepy.OAuth1UserHandler.assert_called_once_with(
            "test_key",
            "test_secret",
            "test_token",
            "test_token_secret",
        )
        mock_tweepy.API.assert_called_once()

        # Verify TweepyClient has both clients
        assert client._client is mock_v2_client
        assert client._api is mock_v1_api


def test_create_from_credentials_requires_api_key() -> None:
    """Factory raises ConfigurationError if API key is missing."""
    credentials = TwitterCredentials(
        api_key=None,
        api_secret="test_secret",
        access_token="test_token",
        access_token_secret="test_token_secret",
    )

    with pytest.raises(ConfigurationError, match="API key and secret are required"):
        TwitterClientFactory.create_from_credentials(credentials)


def test_create_from_credentials_requires_api_secret() -> None:
    """Factory raises ConfigurationError if API secret is missing."""
    credentials = TwitterCredentials(
        api_key="test_key",
        api_secret=None,
        access_token="test_token",
        access_token_secret="test_token_secret",
    )

    with pytest.raises(ConfigurationError, match="API key and secret are required"):
        TwitterClientFactory.create_from_credentials(credentials)


def test_create_from_credentials_requires_access_token() -> None:
    """Factory raises ConfigurationError if access token is missing."""
    credentials = TwitterCredentials(
        api_key="test_key",
        api_secret="test_secret",
        access_token=None,
        access_token_secret="test_token_secret",
    )

    with pytest.raises(ConfigurationError, match="Access token and secret are required"):
        TwitterClientFactory.create_from_credentials(credentials)


def test_create_from_credentials_requires_access_token_secret() -> None:
    """Factory raises ConfigurationError if access token secret is missing."""
    credentials = TwitterCredentials(
        api_key="test_key",
        api_secret="test_secret",
        access_token="test_token",
        access_token_secret=None,
    )

    with pytest.raises(ConfigurationError, match="Access token and secret are required"):
        TwitterClientFactory.create_from_credentials(credentials)


def test_create_from_credentials_bearer_token_is_optional() -> None:
    """Factory works without bearer token (v1.1 only mode)."""
    credentials = TwitterCredentials(
        api_key="test_key",
        api_secret="test_secret",
        access_token="test_token",
        access_token_secret="test_token_secret",
        bearer_token=None,
    )

    with patch("twitter_client.factory.tweepy") as mock_tweepy:
        mock_tweepy.Client.return_value = Mock()
        mock_tweepy.API.return_value = Mock()

        client = TwitterClientFactory.create_from_credentials(credentials)

        # Should pass None for bearer_token
        mock_tweepy.Client.assert_called_once_with(
            bearer_token=None,
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
        )

        assert client is not None
