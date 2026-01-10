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


@dataclass
class ScoredEvent:
    """Event with computed score and metadata."""

    event: DeduplicatedEvent
    score: float
    event_type: str
    impact_level: str  # high, medium, low
    recency_hours: float


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


def score_events(
    events: list[DeduplicatedEvent],
    price_changes: Optional[dict[str, float]] = None,
) -> list[ScoredEvent]:
    """Score all events and return sorted by score.

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
        source_score = calculate_source_score(event)

        # Weighted total
        total_score = (
            recency_score * 0.3
            + impact_score * 0.5
            + source_score * 0.2
        )

        # Bonus for earnings/macro during earnings season
        if event_type in ("earnings", "macro"):
            total_score *= 1.1

        scored.append(
            ScoredEvent(
                event=event,
                score=min(100, total_score),
                event_type=event_type,
                impact_level=impact_level,
                recency_hours=recency_hours,
            )
        )

    # Sort by score descending
    scored.sort(key=lambda x: x.score, reverse=True)

    return scored


def select_top_events(
    scored_events: list[ScoredEvent],
    min_count: int = 5,
    max_count: int = 8,
) -> list[ScoredEvent]:
    """Select top events for article 1.

    Ensures diversity by limiting events per ticker.

    Args:
        scored_events: List of scored events
        min_count: Minimum events to select
        max_count: Maximum events to select

    Returns:
        Selected top events
    """
    selected = []
    ticker_count: dict[str, int] = {}

    for event in scored_events:
        if len(selected) >= max_count:
            break

        # Check ticker diversity (max 2 events per ticker)
        can_add = True
        for ticker in event.event.tickers:
            if ticker_count.get(ticker, 0) >= 2:
                can_add = False
                break

        if can_add:
            selected.append(event)
            for ticker in event.event.tickers:
                ticker_count[ticker] = ticker_count.get(ticker, 0) + 1

    # If we don't have enough, add more without diversity constraint
    if len(selected) < min_count:
        for event in scored_events:
            if event not in selected:
                selected.append(event)
                if len(selected) >= min_count:
                    break

    logger.info(f"Selected {len(selected)} top events")
    return selected
