from __future__ import annotations

from pathlib import Path

import pytest

from twitter_client.config import ConfigManager, TwitterCredentials
from twitter_client.exceptions import ConfigurationError


def test_load_credentials_prefers_environment(tmp_path: Path) -> None:
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text(
        "\n".join(
            [
                "TWITTER_API_KEY=dotenv-key",
                "TWITTER_API_SECRET=dotenv-secret",
                "TWITTER_ACCESS_TOKEN=dotenv-access",
                "TWITTER_ACCESS_TOKEN_SECRET=dotenv-secret-token",
                "TWITTER_BEARER_TOKEN=dotenv-bearer",
            ]
        ),
        encoding="utf-8",
    )
    env = {
        "TWITTER_API_KEY": "env-key",
        "TWITTER_API_SECRET": "env-secret",
        "TWITTER_ACCESS_TOKEN": "env-access",
        "TWITTER_ACCESS_TOKEN_SECRET": "env-access-secret",
        "TWITTER_BEARER_TOKEN": "env-bearer",
    }

    manager = ConfigManager(env=env, dotenv_path=dotenv_file)
    credentials = manager.load_credentials()

    assert credentials.api_key == "env-key"
    assert credentials.access_token == "env-access"


def test_load_credentials_from_dotenv(tmp_path: Path) -> None:
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text(
        "\n".join(
            [
                "TWITTER_API_KEY=dotenv-key",
                "TWITTER_API_SECRET=dotenv-secret",
                "TWITTER_ACCESS_TOKEN=dotenv-access",
                "TWITTER_ACCESS_TOKEN_SECRET=dotenv-access-secret",
                "TWITTER_BEARER_TOKEN=dotenv-bearer",
            ]
        ),
        encoding="utf-8",
    )

    manager = ConfigManager(env={}, dotenv_path=dotenv_file)
    credentials = manager.load_credentials(priority=("dotenv",))

    assert credentials.api_key == "dotenv-key"
    assert credentials.access_token_secret == "dotenv-access-secret"


def test_load_credentials_raises_when_missing(tmp_path: Path) -> None:
    dotenv_file = tmp_path / ".env"
    manager = ConfigManager(env={}, dotenv_path=dotenv_file)

    with pytest.raises(ConfigurationError):
        manager.load_credentials()


def test_save_credentials_updates_dotenv(tmp_path: Path) -> None:
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text(
        "\n".join(
            [
                "# Existing credentials",
                "TWITTER_API_KEY=existing-key",
                "TWITTER_API_SECRET=existing-secret",
            ]
        ),
        encoding="utf-8",
    )
    manager = ConfigManager(env={}, dotenv_path=dotenv_file)

    manager.save_credentials(
        TwitterCredentials(
            api_key="existing-key",
            api_secret="existing-secret",
            access_token="new-access",
            access_token_secret="new-secret",
        )
    )

    contents = dotenv_file.read_text(encoding="utf-8")
    assert "TWITTER_API_KEY=existing-key" in contents
    assert "TWITTER_API_SECRET=existing-secret" in contents
    assert "TWITTER_ACCESS_TOKEN=new-access" in contents
    assert "TWITTER_ACCESS_TOKEN_SECRET=new-secret" in contents
