"""
Factory for creating X client instances with proper initialization.
"""

from __future__ import annotations

import tweepy

from x_client.clients.rate_limited_client import RateLimitedClient
from x_client.clients.tweepy_client import TweepyClient
from x_client.config import ConfigManager, XCredentials
from x_client.exceptions import ConfigurationError
from x_client.rate_limit import RetryConfig


class XClientFactory:
    """Factory for creating properly initialized X API clients."""

    @staticmethod
    def create_from_config(
        config_manager: ConfigManager,
        enable_rate_limiting: bool = True,
        retry_config: RetryConfig | None = None,
    ) -> TweepyClient | RateLimitedClient:
        """
        Create TweepyClient with both v2 and v1.1 API instances.

        Args:
            config_manager: ConfigManager instance with loaded credentials
            enable_rate_limiting: Whether to wrap client with rate limiting (default: True)
            retry_config: Optional retry configuration for rate limiting

        Returns:
            Fully initialized TweepyClient (optionally wrapped with RateLimitedClient)

        Raises:
            ConfigurationError: If credentials are missing or invalid
        """
        credentials = config_manager.load_credentials()
        return XClientFactory.create_from_credentials(
            credentials,
            enable_rate_limiting=enable_rate_limiting,
            retry_config=retry_config,
        )

    @staticmethod
    def create_from_credentials(
        credentials: XCredentials,
        enable_rate_limiting: bool = True,
        retry_config: RetryConfig | None = None,
    ) -> TweepyClient | RateLimitedClient:
        """
        Create TweepyClient directly from credentials.

        Args:
            credentials: XCredentials with OAuth tokens
            enable_rate_limiting: Whether to wrap client with rate limiting (default: True)
            retry_config: Optional retry configuration for rate limiting

        Returns:
            Fully initialized TweepyClient (optionally wrapped with RateLimitedClient)

        Raises:
            ConfigurationError: If required credentials are missing
        """
        # Validate required credentials
        if not credentials.api_key or not credentials.api_secret:
            raise ConfigurationError("API key and secret are required")

        if not credentials.access_token or not credentials.access_token_secret:
            raise ConfigurationError("Access token and secret are required")

        # Initialize v2 client for post operations
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

        client = TweepyClient(v2_client, v1_api)

        # Optionally wrap with rate limiting
        if enable_rate_limiting:
            return RateLimitedClient(client, retry_config=retry_config)

        return client
