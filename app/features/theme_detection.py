"""Theme detection for article 3.

Detects themes based on:
- News headline keywords
- Sector/industry movers
- Pre-defined theme mappings
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Theme keyword mappings
THEME_KEYWORDS = {
    "ai-server": {
        "keywords": ["ai server", "gpu", "data center", "hbm", "cowos", "nvidia", "amd gpu"],
        "display": "AI 伺服器供應鏈",
        "tickers": ["NVDA", "AMD", "TSM", "AVGO", "MU", "SMCI"],
    },
    "ai-software": {
        "keywords": ["ai software", "chatgpt", "copilot", "generative ai", "llm", "openai"],
        "display": "AI 軟體與應用",
        "tickers": ["MSFT", "GOOGL", "META", "CRM", "ADBE", "NOW"],
    },
    "semiconductor": {
        "keywords": ["semiconductor", "chip", "wafer", "foundry", "tsmc", "asml"],
        "display": "半導體產業",
        "tickers": ["TSM", "ASML", "AMAT", "LRCX", "KLAC", "INTC"],
    },
    "ev": {
        "keywords": ["electric vehicle", "ev", "tesla", "battery", "charging"],
        "display": "電動車產業",
        "tickers": ["TSLA", "RIVN", "LCID", "NIO", "LI", "XPEV"],
    },
    "cloud": {
        "keywords": ["cloud", "aws", "azure", "gcp", "saas", "iaas"],
        "display": "雲端運算",
        "tickers": ["AMZN", "MSFT", "GOOGL", "CRM", "NOW", "SNOW"],
    },
    "biotech": {
        "keywords": ["biotech", "pharma", "drug", "fda", "clinical trial", "obesity"],
        "display": "生技製藥",
        "tickers": ["LLY", "NVO", "AMGN", "GILD", "BIIB", "MRNA"],
    },
    "fintech": {
        "keywords": ["fintech", "payment", "crypto", "bitcoin", "blockchain"],
        "display": "金融科技",
        "tickers": ["V", "MA", "PYPL", "SQ", "COIN", "HOOD"],
    },
}


@dataclass
class DetectedTheme:
    """Detected theme for article 3."""

    theme_id: str
    display_name: str
    score: float
    matched_keywords: list[str]
    relevant_tickers: list[str]
    trigger_events: list[str]


def detect_themes(
    headlines: list[str],
    ticker_counts: dict[str, int],
    limit: int = 3,
) -> list[DetectedTheme]:
    """Detect themes from news headlines and ticker activity.

    Args:
        headlines: List of news headlines
        ticker_counts: Dict of ticker -> mention count
        limit: Maximum themes to return

    Returns:
        List of detected themes, sorted by score
    """
    combined_text = " ".join(headlines).lower()
    themes = []

    for theme_id, config in THEME_KEYWORDS.items():
        matched = []
        trigger_events = []

        # Check keywords
        for keyword in config["keywords"]:
            if keyword in combined_text:
                matched.append(keyword)
                # Find headlines with this keyword
                for h in headlines:
                    if keyword in h.lower() and h not in trigger_events:
                        trigger_events.append(h)
                        if len(trigger_events) >= 3:
                            break

        # Check ticker activity
        theme_tickers = config["tickers"]
        active_tickers = [t for t in theme_tickers if ticker_counts.get(t, 0) > 0]

        # Calculate score
        keyword_score = len(matched) * 20
        ticker_score = len(active_tickers) * 15
        total_score = keyword_score + ticker_score

        if total_score > 0:
            themes.append(
                DetectedTheme(
                    theme_id=theme_id,
                    display_name=config["display"],
                    score=total_score,
                    matched_keywords=matched,
                    relevant_tickers=active_tickers or theme_tickers[:3],
                    trigger_events=trigger_events[:3],
                )
            )

    # Sort by score
    themes.sort(key=lambda x: x.score, reverse=True)

    return themes[:limit]


def select_theme(themes: list[DetectedTheme]) -> Optional[DetectedTheme]:
    """Select the best theme for today's article 3."""
    if not themes:
        # Default fallback
        return DetectedTheme(
            theme_id="ai-server",
            display_name="AI 伺服器供應鏈",
            score=0,
            matched_keywords=[],
            relevant_tickers=["NVDA", "AMD", "TSM"],
            trigger_events=["AI 需求持續成長"],
        )

    return themes[0]
