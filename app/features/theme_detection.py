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


# ===========================================
# Embedding-based theme detection (optional)
# ===========================================

# Theme reference texts for embedding comparison
THEME_REFERENCE_TEXTS = {
    "ai-server": "AI server GPU data center NVIDIA AMD HBM CoWoS advanced packaging semiconductor infrastructure",
    "ai-software": "generative AI ChatGPT Copilot LLM machine learning software enterprise AI SaaS",
    "semiconductor": "semiconductor chip wafer foundry TSMC Intel Samsung advanced node lithography",
    "ev": "electric vehicle Tesla EV battery charging station autonomous driving BYD",
    "cloud": "cloud computing AWS Azure GCP SaaS IaaS infrastructure digital transformation",
    "biotech": "biotech pharmaceutical FDA drug clinical trial obesity treatment GLP-1",
    "fintech": "fintech payment digital banking cryptocurrency blockchain DeFi mobile payment",
}


def get_embedding(text: str, llm_client=None) -> Optional[list[float]]:
    """Get embedding vector for text using LLM.

    Args:
        text: Text to embed
        llm_client: Optional LLM client

    Returns:
        Embedding vector, or None if failed
    """
    if llm_client is None:
        try:
            from app.llm.client import get_llm_client
            llm_client = get_llm_client()
        except Exception:
            return None

    if not llm_client:
        return None

    try:
        # Use OpenAI-compatible embedding endpoint
        from openai import OpenAI

        client = OpenAI(
            api_key=llm_client.config.api_key,
            base_url=llm_client.config.api_url,
        )

        response = client.embeddings.create(
            model="text-embedding-3-small",  # or available model
            input=text[:8000],
        )

        return response.data[0].embedding
    except Exception as e:
        logger.debug(f"Failed to get embedding: {e}")
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    import math

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def detect_themes_with_embeddings(
    headlines: list[str],
    ticker_counts: dict[str, int] = None,
    limit: int = 3,
) -> list[DetectedTheme]:
    """Detect themes using embedding similarity (enhanced version).

    Falls back to keyword-based detection if embeddings fail.

    Args:
        headlines: List of news headlines
        ticker_counts: Dict of ticker -> mention count
        limit: Maximum themes to return

    Returns:
        List of detected themes, sorted by score
    """
    if ticker_counts is None:
        ticker_counts = {}

    # Try embedding-based detection
    combined_text = " ".join(headlines)
    headline_embedding = get_embedding(combined_text)

    if headline_embedding is None:
        # Fallback to keyword-based
        logger.info("Using keyword-based theme detection (embeddings unavailable)")
        return detect_themes(headlines, ticker_counts, limit)

    logger.info("Using embedding-based theme detection")

    themes = []

    for theme_id, config in THEME_KEYWORDS.items():
        # Get reference embedding
        ref_text = THEME_REFERENCE_TEXTS.get(theme_id, " ".join(config["keywords"]))
        ref_embedding = get_embedding(ref_text)

        if ref_embedding is None:
            continue

        # Calculate similarity
        similarity = cosine_similarity(headline_embedding, ref_embedding)

        # Check keyword matches (for trigger events)
        combined_lower = combined_text.lower()
        matched = [kw for kw in config["keywords"] if kw in combined_lower]

        trigger_events = []
        for keyword in matched[:3]:
            for h in headlines:
                if keyword in h.lower() and h not in trigger_events:
                    trigger_events.append(h)
                    break

        # Check ticker activity
        theme_tickers = config["tickers"]
        active_tickers = [t for t in theme_tickers if ticker_counts.get(t, 0) > 0]

        # Combined score: embedding similarity + ticker activity
        embedding_score = similarity * 100
        ticker_score = len(active_tickers) * 10
        total_score = embedding_score + ticker_score

        if total_score > 20:  # Threshold
            themes.append(
                DetectedTheme(
                    theme_id=theme_id,
                    display_name=config["display"],
                    score=total_score,
                    matched_keywords=matched,
                    relevant_tickers=active_tickers or theme_tickers[:3],
                    trigger_events=trigger_events[:3] or ["相關新聞報導"],
                )
            )

    # Sort by score
    themes.sort(key=lambda x: x.score, reverse=True)

    if not themes:
        # Fallback to keyword-based if no themes detected
        return detect_themes(headlines, ticker_counts, limit)

    return themes[:limit]
