from __future__ import annotations

import json
from pathlib import Path

import pytest

from twitter_client.config import ConfigManager, TwitterCredentials
from twitter_client.exceptions import ConfigurationError


def test_load_credentials_prefers_environment(tmp_path: Path) -> None:
    env = {
        "TWITTER_API_KEY": "env-key",
        "TWITTER_API_SECRET": "env-secret",
        "TWITTER_ACCESS_TOKEN": "env-access",
        "TWITTER_ACCESS_TOKEN_SECRET": "env-secret-token",
        "TWITTER_BEARER_TOKEN": "env-bearer",
    }
    credential_path = tmp_path / "twitter.json"
    credential_path.write_text(
        json.dumps(
            {
                "api_key": "file-key",
                "api_secret": "file-secret",
                "access_token": "file-access",
                "access_token_secret": "file-access-secret",
            }
        ),
        encoding="utf-8",
    )

    manager = ConfigManager(credential_path=credential_path, env=env)
    credentials = manager.load_credentials()

    assert credentials.api_key == "env-key"
    assert credentials.access_token == "env-access"


def test_load_credentials_from_file_when_env_empty(tmp_path: Path) -> None:
    credential_path = tmp_path / "twitter.json"
    credential_path.write_text(
        json.dumps(
            {
                "api_key": "file-key",
                "api_secret": "file-secret",
                "access_token": "file-access",
                "access_token_secret": "file-access-secret",
            }
        ),
        encoding="utf-8",
    )

    manager = ConfigManager(credential_path=credential_path, env={})
    credentials = manager.load_credentials(priority=("file",))

    assert credentials.api_key == "file-key"
    assert credentials.access_token_secret == "file-access-secret"


def test_load_credentials_from_dotenv(tmp_path: Path) -> None:
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text(
        """
TWITTER_API_KEY=dotenv-key
TWITTER_API_SECRET=dotenv-secret
TWITTER_ACCESS_TOKEN=dotenv-access
TWITTER_ACCESS_TOKEN_SECRET=dotenv-access-secret
TWITTER_BEARER_TOKEN=dotenv-bearer
""".strip()
    )

    manager = ConfigManager(credential_path=tmp_path / "credentials.json", env={}, dotenv_path=dotenv_file)
    credentials = manager.load_credentials(priority=("dotenv",))

    assert credentials.api_key == "dotenv-key"
    assert credentials.access_token_secret == "dotenv-access-secret"


def test_load_credentials_raises_when_missing(tmp_path: Path) -> None:
    manager = ConfigManager(credential_path=tmp_path / "twitter.json", env={})

    with pytest.raises(ConfigurationError):
        manager.load_credentials()


def test_save_credentials_merges_existing_values(tmp_path: Path) -> None:
    credential_path = tmp_path / "twitter.json"
    credential_path.write_text(
        json.dumps(
            {
                "api_key": "existing-key",
                "api_secret": "existing-secret",
                "access_token": "existing-access",
            }
        ),
        encoding="utf-8",
    )
    manager = ConfigManager(credential_path=credential_path, env={})

    manager.save_credentials(
        TwitterCredentials(
            access_token="new-access",
            access_token_secret="new-secret",
        )
    )

    data = json.loads(credential_path.read_text(encoding="utf-8"))
    assert data["api_key"] == "existing-key"
    assert data["access_token"] == "new-access"
    assert data["access_token_secret"] == "new-secret"
