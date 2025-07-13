import importlib
import os
import pytest

import main


def test_validate_config_success(monkeypatch):
    monkeypatch.setenv("API_ID", "123")
    monkeypatch.setenv("API_HASH", "hash")
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("CHANNEL_USERNAME", "chan")
    monkeypatch.setenv("SHEET_URL", "url")
    monkeypatch.setenv("GOOGLE_CREDENTIALS", "/tmp/creds.json")
    importlib.reload(main)
    config = main.validate_config()
    assert config["API_ID"] == 123


def test_validate_config_missing(monkeypatch):
    monkeypatch.setenv("API_HASH", "hash")
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("CHANNEL_USERNAME", "chan")
    monkeypatch.setenv("SHEET_URL", "url")
    monkeypatch.setenv("GOOGLE_CREDENTIALS", "/tmp/creds.json")
    importlib.reload(main)
    monkeypatch.delenv("API_ID", raising=False)
    with pytest.raises(SystemExit):
        main.validate_config()
