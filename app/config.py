"""Configuration management for Rocket Screener.

All secrets are loaded from environment variables.
Never hardcode API keys or tokens.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

# Timezone for all operations
TZ = ZoneInfo("Asia/Taipei")


@dataclass
class GhostConfig:
    """Ghost CMS configuration."""

    admin_api_url: str
    admin_api_key: str
    newsletter_slug: str = "default-newsletter"
    email_segment: str = "status:free"

    @classmethod
    def from_env(cls) -> "GhostConfig":
        """Load Ghost config from environment variables."""
        admin_api_url = os.environ.get("GHOST_ADMIN_API_URL")
        admin_api_key = os.environ.get("GHOST_ADMIN_API_KEY")

        if not admin_api_url or not admin_api_key:
            raise ValueError(
                "Missing required environment variables: "
                "GHOST_ADMIN_API_URL and GHOST_ADMIN_API_KEY"
            )

        return cls(
            admin_api_url=admin_api_url,
            admin_api_key=admin_api_key,
            newsletter_slug=os.environ.get("NEWSLETTER_SLUG", "default-newsletter"),
            email_segment=os.environ.get("EMAIL_SEGMENT", "status:free"),
        )


@dataclass
class FMPConfig:
    """Financial Modeling Prep API configuration.

    Uses /stable/ endpoints only. See FMP_STABLE_API_REFERENCE.md.
    """

    api_key: str
    base_url: str = "https://financialmodelingprep.com"

    @classmethod
    def from_env(cls) -> "FMPConfig":
        """Load FMP config from environment variables."""
        api_key = os.environ.get("FMP_API_KEY")
        if not api_key:
            raise ValueError("Missing required environment variable: FMP_API_KEY")
        return cls(api_key=api_key)


@dataclass
class TranscriptConfig:
    """Earnings call transcript API configuration."""

    api_url: str
    api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "TranscriptConfig":
        """Load transcript config from environment variables."""
        api_url = os.environ.get("TRANSCRIPT_API_URL", "")
        api_key = os.environ.get("TRANSCRIPT_API_KEY")
        return cls(api_url=api_url, api_key=api_key)


@dataclass
class LiteLLMConfig:
    """LiteLLM unified proxy configuration."""

    api_url: str
    api_key: str
    model: str = "cli-gpt-5.2"

    @classmethod
    def from_env(cls) -> Optional["LiteLLMConfig"]:
        """Load LiteLLM config from environment variables."""
        api_url = os.environ.get("LITELLM_API_URL")
        api_key = os.environ.get("LITELLM_API_KEY")
        if not api_url or not api_key:
            return None
        model = os.environ.get("LITELLM_MODEL", "cli-gpt-5.2")
        return cls(api_url=api_url, api_key=api_key, model=model)


@dataclass
class MemberWallConfig:
    """Member wall (paywall) configuration."""

    enabled: bool = False
    article2_members_only: bool = False  # Article 2 behind paywall
    article3_members_only: bool = False  # Article 3 behind paywall

    @classmethod
    def from_env(cls) -> "MemberWallConfig":
        """Load member wall config from environment variables."""
        enabled = os.environ.get("MEMBER_WALL_ENABLED", "").lower() in ("true", "1", "yes")
        article2 = os.environ.get("ARTICLE2_MEMBERS_ONLY", "").lower() in ("true", "1", "yes")
        article3 = os.environ.get("ARTICLE3_MEMBERS_ONLY", "").lower() in ("true", "1", "yes")
        return cls(enabled=enabled, article2_members_only=article2, article3_members_only=article3)


@dataclass
class AppConfig:
    """Main application configuration."""

    ghost: GhostConfig
    fmp: Optional[FMPConfig] = None
    transcript: Optional[TranscriptConfig] = None
    litellm: Optional[LiteLLMConfig] = None
    member_wall: Optional[MemberWallConfig] = None
    output_dir: Path = Path("out")
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load all configuration from environment variables."""
        ghost = GhostConfig.from_env()

        # FMP is optional for v1
        fmp = None
        if os.environ.get("FMP_API_KEY"):
            fmp = FMPConfig.from_env()

        # Transcript is optional for v1
        transcript = None
        if os.environ.get("TRANSCRIPT_API_URL"):
            transcript = TranscriptConfig.from_env()

        # LiteLLM for LLM-based content generation
        litellm = LiteLLMConfig.from_env()

        # Member wall configuration
        member_wall = MemberWallConfig.from_env()

        output_dir = Path(os.environ.get("OUTPUT_DIR", "out"))
        log_level = os.environ.get("LOG_LEVEL", "INFO")

        return cls(
            ghost=ghost,
            fmp=fmp,
            transcript=transcript,
            litellm=litellm,
            member_wall=member_wall,
            output_dir=output_dir,
            log_level=log_level,
        )


def load_config() -> AppConfig:
    """Load configuration from environment.

    This function loads .env file if it exists, then creates AppConfig.
    """
    from dotenv import load_dotenv

    # Load .env file if exists
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    return AppConfig.from_env()
