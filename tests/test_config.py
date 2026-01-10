"""Tests for configuration module."""

import os

import pytest


class TestGhostConfig:
    """Test Ghost configuration."""

    def test_from_env_success(self, monkeypatch):
        """Should load config from environment."""
        from app.config import GhostConfig

        monkeypatch.setenv("GHOST_ADMIN_API_URL", "https://test.ghost.io")
        monkeypatch.setenv("GHOST_ADMIN_API_KEY", "abc123:secret456")

        config = GhostConfig.from_env()
        assert config.admin_api_url == "https://test.ghost.io"
        assert config.admin_api_key == "abc123:secret456"

    def test_from_env_missing_url(self, monkeypatch):
        """Should raise error if URL is missing."""
        from app.config import GhostConfig

        monkeypatch.delenv("GHOST_ADMIN_API_URL", raising=False)
        monkeypatch.setenv("GHOST_ADMIN_API_KEY", "abc123:secret456")

        with pytest.raises(ValueError, match="Missing required environment variables"):
            GhostConfig.from_env()

    def test_from_env_missing_key(self, monkeypatch):
        """Should raise error if key is missing."""
        from app.config import GhostConfig

        monkeypatch.setenv("GHOST_ADMIN_API_URL", "https://test.ghost.io")
        monkeypatch.delenv("GHOST_ADMIN_API_KEY", raising=False)

        with pytest.raises(ValueError, match="Missing required environment variables"):
            GhostConfig.from_env()

    def test_default_newsletter_slug(self, monkeypatch):
        """Should use default newsletter slug if not set."""
        from app.config import GhostConfig

        monkeypatch.setenv("GHOST_ADMIN_API_URL", "https://test.ghost.io")
        monkeypatch.setenv("GHOST_ADMIN_API_KEY", "abc123:secret456")
        monkeypatch.delenv("NEWSLETTER_SLUG", raising=False)

        config = GhostConfig.from_env()
        assert config.newsletter_slug == "default-newsletter"


class TestFMPConfig:
    """Test FMP configuration."""

    def test_from_env_success(self, monkeypatch):
        """Should load FMP config from environment."""
        from app.config import FMPConfig

        monkeypatch.setenv("FMP_API_KEY", "test-fmp-key")

        config = FMPConfig.from_env()
        assert config.api_key == "test-fmp-key"

    def test_from_env_missing_key(self, monkeypatch):
        """Should raise error if key is missing."""
        from app.config import FMPConfig

        monkeypatch.delenv("FMP_API_KEY", raising=False)

        with pytest.raises(ValueError, match="Missing required environment variable"):
            FMPConfig.from_env()
