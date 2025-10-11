"""
Factory for creating Twitter client instances with proper initialization.
"""

from __future__ import annotations

import tweepy

from twitter_client.clients.tweepy_client import TweepyClient
from twitter_client.config import ConfigManager, TwitterCredentials
from twitter_client.exceptions import ConfigurationError


class TwitterClientFactory:
    """Factory for creating properly initialized Twitter API clients."""

    @staticmethod
    def create_from_config(config_manager: ConfigManager) -> TweepyClient:
        """
        Create TweepyClient with both v2 and v1.1 API instances.

        Args:
            config_manager: ConfigManager instance with loaded credentials

        Returns:
            Fully initialized TweepyClient with dual-client architecture

        Raises:
            ConfigurationError: If credentials are missing or invalid
        """
        credentials = config_manager.load_credentials()
        return TwitterClientFactory.create_from_credentials(credentials)

    @staticmethod
    def create_from_credentials(credentials: TwitterCredentials) -> TweepyClient:
        """
        Create TweepyClient directly from credentials.

        Args:
            credentials: TwitterCredentials with OAuth tokens

        Returns:
            Fully initialized TweepyClient

        Raises:
            ConfigurationError: If required credentials are missing
        """
        # Validate required credentials
        if not credentials.api_key or not credentials.api_secret:
            raise ConfigurationError("API key and secret are required")

        if not credentials.access_token or not credentials.access_token_secret:
            raise ConfigurationError("Access token and secret are required")

        # Initialize v2 client for tweet operations
        v2_client = tweepy.Client(
            bearer_token=credentials.bearer_token,
            consumer_key=credentials.api_key,
            consumer_secret=credentials.api_secret,
            access_token=credentials.access_token,
            access_token_secret=credentials.access_token_secret,
        )

        # Initialize v1.1 API for media operations
        auth = tweepy.OAuth1UserHandler(
            credentials.api_key,
            credentials.api_secret,
            credentials.access_token,
            credentials.access_token_secret,
        )
        v1_api = tweepy.API(auth)

        return TweepyClient(v2_client, v1_api)
