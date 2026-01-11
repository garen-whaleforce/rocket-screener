"""Event scoring for article 1 (daily brief).

Scores events based on:
- Relevance (ticker importance, sector)
- Recency (time since published)
- Impact (price move, news type)
- Uniqueness (not common/repeated news)
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from app.normalize.dedupe import DeduplicatedEvent

logger = logging.getLogger(__name__)

# Event type keywords for classification
EVENT_TYPE_KEYWORDS = {
    "earnings": [
        "earnings", "revenue", "profit", "loss", "eps", "beat", "miss",
        "quarterly", "q1", "q2", "q3", "q4", "guidance", "outlook",
        "財報", "營收", "獲利",
    ],
    "macro": [
        "fed", "fomc", "rate", "inflation", "cpi", "ppi", "gdp", "jobs",
        "employment", "unemployment", "treasury", "yield", "bond",
        "利率", "通膨", "就業",
    ],
    "policy": [
        "regulation", "policy", "law", "congress", "senate", "house",
        "tariff", "sanction", "antitrust", "sec", "ftc",
        "政策", "監管", "關稅",
    ],
    "mna": [
        "merger", "acquisition", "acquire", "takeover", "buyout", "deal",
        "bid", "offer", "purchase",
        "併購", "收購",
    ],
    "product": [
        "launch", "announce", "unveil", "release", "new product", "innovation",
        "發布", "推出",
    ],
    "legal": [
        "lawsuit", "sue", "court", "settlement", "fine", "penalty",
        "訴訟", "罰款",
    ],
}

# High-impact tickers (mega caps, market movers)
HIGH_IMPACT_TICKERS = {
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA",
    "BRK.A", "BRK.B", "JPM", "JNJ", "V", "UNH", "HD", "PG",
    "MA", "DIS", "NFLX", "AMD", "INTC", "CRM", "ADBE", "PYPL",
}

# Source quality scoring
# Denylist: PR wires, YouTube, low-signal sources (score penalty)
SOURCE_DENYLIST = {
    "globenewswire.com": -30,      # PR wire, paid press releases
    "businesswire.com": -30,       # PR wire
    "prnewswire.com": -30,         # PR wire
    "youtube.com": -40,            # Video content, not primary source
    "accesswire.com": -25,         # PR wire
    "newsfilecorp.com": -25,       # PR wire
    "streetinsider.com": -10,      # Aggregator
}

# Allowlist: High-quality financial media (score bonus)
SOURCE_ALLOWLIST = {
    "reuters.com": 20,             # Primary news source
    "cnbc.com": 15,                # Major financial media
    "bloomberg.com": 20,           # Premium financial news
    "wsj.com": 20,                 # Wall Street Journal
    "sec.gov": 25,                 # Official SEC filings
    "ir.": 15,                     # Investor relations (prefix match)
    "seekingalpha.com": 10,        # Analysis site
    "thestreet.com": 10,           # Financial news
    "marketwatch.com": 15,         # Financial news
    "ft.com": 20,                  # Financial Times
    "barrons.com": 15,             # Barron's
}


@dataclass
class ScoredEvent:
    """Event with computed score and metadata."""

    event: DeduplicatedEvent
    score: float
    event_type: str
    impact_level: str  # high, medium, low
    recency_hours: float
    # Source quality fields
    price_score: float = 0.0
    recency_score: float = 0.0
    novelty_score: float = 0.0
    source_quality_score: float = 0.0
    is_low_quality_source: bool = False


def classify_event_type(headline: str, text: str) -> str:
    """Classify event type based on keywords."""
    combined = (headline + " " + text).lower()

    for event_type, keywords in EVENT_TYPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in combined:
                return event_type

    return "other"


def calculate_recency_score(published_date: str) -> tuple[float, float]:
    """Calculate recency score (0-100) and hours since published.

    More recent = higher score.
    """
    try:
        dt = datetime.fromisoformat(published_date.replace("Z", "+00:00"))
    except ValueError:
        # Default to 24 hours ago if can't parse
        return 50.0, 24.0

    now = datetime.now(ZoneInfo("UTC"))
    delta = now - dt.replace(tzinfo=ZoneInfo("UTC")) if dt.tzinfo is None else now - dt

    hours = delta.total_seconds() / 3600

    # Score: 100 for < 1 hour, decreasing to 0 at 48 hours
    if hours <= 1:
        score = 100
    elif hours <= 6:
        score = 90 - (hours - 1) * 2
    elif hours <= 12:
        score = 80 - (hours - 6) * 2
    elif hours <= 24:
        score = 68 - (hours - 12) * 2
    elif hours <= 48:
        score = 44 - (hours - 24)
    else:
        score = max(0, 20 - (hours - 48) * 0.5)

    return score, hours


def calculate_impact_score(
    event: DeduplicatedEvent,
    price_changes: Optional[dict[str, float]] = None,
) -> tuple[float, str]:
    """Calculate impact score based on tickers and price moves.

    Args:
        event: The event
        price_changes: Optional dict of ticker -> price change %

    Returns:
        (score, impact_level)
    """
    # Base score from ticker importance
    ticker_score = 0
    for ticker in event.tickers:
        if ticker in HIGH_IMPACT_TICKERS:
            ticker_score += 30
        else:
            ticker_score += 10

    # Cap at 50
    ticker_score = min(50, ticker_score)

    # Price move score
    price_score = 0
    if price_changes:
        for ticker in event.tickers:
            if ticker in price_changes:
                abs_change = abs(price_changes[ticker])
                if abs_change >= 10:
                    price_score = max(price_score, 50)
                elif abs_change >= 5:
                    price_score = max(price_score, 40)
                elif abs_change >= 3:
                    price_score = max(price_score, 30)
                elif abs_change >= 2:
                    price_score = max(price_score, 20)
                elif abs_change >= 1:
                    price_score = max(price_score, 10)

    total = ticker_score + price_score

    # Determine impact level
    if total >= 70:
        level = "high"
    elif total >= 40:
        level = "medium"
    else:
        level = "low"

    return total, level


def calculate_source_score(event: DeduplicatedEvent) -> float:
    """Calculate score based on number of sources.

    Multiple sources = more important.
    """
    num_sources = len(event.source_urls)
    if num_sources >= 5:
        return 30
    elif num_sources >= 3:
        return 20
    elif num_sources >= 2:
        return 10
    return 0


def calculate_source_quality_score(event: DeduplicatedEvent) -> tuple[float, bool]:
    """Calculate source quality score based on denylist/allowlist.

    Args:
        event: The event with source URLs

    Returns:
        (quality_score, is_low_quality)
        - quality_score: Positive for good sources, negative for bad
        - is_low_quality: True if primary source is from denylist
    """
    quality_score = 0
    is_low_quality = False

    # Get primary source (first URL or site field)
    primary_source = ""
    if event.source_urls:
        primary_source = event.source_urls[0].lower()

    # Check all sources
    all_sources = [url.lower() for url in event.source_urls]

    # Check denylist (penalty)
    for source in all_sources:
        for deny_domain, penalty in SOURCE_DENYLIST.items():
            if deny_domain in source:
                quality_score += penalty
                if deny_domain in primary_source:
                    is_low_quality = True
                break

    # Check allowlist (bonus)
    for source in all_sources:
        for allow_domain, bonus in SOURCE_ALLOWLIST.items():
            if allow_domain in source:
                quality_score += bonus
                break

    return quality_score, is_low_quality


def score_events(
    events: list[DeduplicatedEvent],
    price_changes: Optional[dict[str, float]] = None,
) -> list[ScoredEvent]:
    """Score all events and return sorted by score.

    Scoring includes:
    - Recency (30%): More recent = higher score
    - Impact (40%): Ticker importance + price moves
    - Source count (15%): Multiple sources = more important
    - Source quality (15%): Allowlist bonus, denylist penalty

    Args:
        events: List of deduplicated events
        price_changes: Optional dict of ticker -> price change %

    Returns:
        List of scored events, sorted by score descending
    """
    scored = []

    for event in events:
        # Classify event type
        event_type = classify_event_type(event.headline, event.text)

        # Calculate component scores
        recency_score, recency_hours = calculate_recency_score(event.published_date)
        impact_score, impact_level = calculate_impact_score(event, price_changes)
        source_count_score = calculate_source_score(event)
        source_quality_score, is_low_quality = calculate_source_quality_score(event)

        # Weighted total (recency 30%, impact 40%, source 15%, quality 15%)
        # Source quality score can be negative (penalty) or positive (bonus)
        base_score = (
            recency_score * 0.30
            + impact_score * 0.40
            + source_count_score * 0.15
        )

        # Apply source quality adjustment (can push score down significantly)
        # Normalize quality score to -30 to +30 range impact
        quality_adjustment = max(-30, min(30, source_quality_score * 0.15))
        total_score = base_score + quality_adjustment

        # Bonus for earnings/macro during earnings season
        if event_type in ("earnings", "macro"):
            total_score *= 1.1

        # Cap at 0-100
        total_score = max(0, min(100, total_score))

        scored.append(
            ScoredEvent(
                event=event,
                score=total_score,
                event_type=event_type,
                impact_level=impact_level,
                recency_hours=recency_hours,
                recency_score=recency_score,
                price_score=impact_score,
                source_quality_score=source_quality_score,
                is_low_quality_source=is_low_quality,
            )
        )

    # Sort by score descending
    scored.sort(key=lambda x: x.score, reverse=True)

    return scored


def select_top_events(
    scored_events: list[ScoredEvent],
    min_count: int = 5,
    max_count: int = 8,
    max_low_quality: int = 2,
) -> list[ScoredEvent]:
    """Select top events for article 1.

    Selection criteria:
    - Score-based ranking
    - Ticker diversity (max 2 events per ticker)
    - Source quality filter (limit low-quality sources in Top 8)

    Args:
        scored_events: List of scored events
        min_count: Minimum events to select
        max_count: Maximum events to select
        max_low_quality: Maximum low-quality sources allowed in Top 8

    Returns:
        Selected top events
    """
    selected = []
    ticker_count: dict[str, int] = {}
    low_quality_count = 0

    for event in scored_events:
        if len(selected) >= max_count:
            break

        # Check ticker diversity (max 2 events per ticker)
        can_add = True
        for ticker in event.event.tickers:
            if ticker_count.get(ticker, 0) >= 2:
                can_add = False
                break

        # Check source quality (limit low-quality in Top 8)
        if event.is_low_quality_source:
            if low_quality_count >= max_low_quality:
                can_add = False
                logger.debug(f"Skipping low-quality source: {event.event.headline[:50]}...")

        if can_add:
            selected.append(event)
            for ticker in event.event.tickers:
                ticker_count[ticker] = ticker_count.get(ticker, 0) + 1
            if event.is_low_quality_source:
                low_quality_count += 1

    # If we don't have enough, add more (relax constraints)
    if len(selected) < min_count:
        for event in scored_events:
            if event not in selected:
                selected.append(event)
                if len(selected) >= min_count:
                    break

    # Log selection summary
    high_quality = len([e for e in selected if not e.is_low_quality_source])
    logger.info(f"Selected {len(selected)} top events ({high_quality} high-quality)")
    return selected
