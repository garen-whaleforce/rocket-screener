"""News deduplication and merging.

Handles:
- Same URL deduplication
- Similar title merging (fuzzy match)
- Multi-source consolidation
"""

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional

from app.ingest.fmp_client import NewsItem

logger = logging.getLogger(__name__)


@dataclass
class DeduplicatedEvent:
    """Deduplicated news event with merged sources."""

    headline: str
    text: str
    source_urls: list[str]
    sources: list[str]
    tickers: list[str]
    published_date: str
    original_items: list[NewsItem] = field(default_factory=list)


def normalize_title(title: str) -> str:
    """Normalize title for comparison.

    - Lowercase
    - Remove punctuation
    - Remove common noise words
    """
    # Lowercase
    title = title.lower()

    # Remove punctuation
    title = re.sub(r"[^\w\s]", " ", title)

    # Remove multiple spaces
    title = re.sub(r"\s+", " ", title).strip()

    # Remove common noise words
    noise_words = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or"}
    words = [w for w in title.split() if w not in noise_words]

    return " ".join(words)


def title_similarity(title1: str, title2: str) -> float:
    """Calculate similarity ratio between two titles."""
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)
    return SequenceMatcher(None, norm1, norm2).ratio()


def deduplicate_news(
    news_items: list[NewsItem],
    similarity_threshold: float = 0.7,
) -> list[DeduplicatedEvent]:
    """Deduplicate and merge news items.

    Args:
        news_items: List of news items
        similarity_threshold: Minimum similarity to consider as duplicate

    Returns:
        List of deduplicated events
    """
    if not news_items:
        return []

    # First pass: dedupe by URL
    seen_urls = set()
    unique_by_url = []
    for item in news_items:
        if item.url not in seen_urls:
            seen_urls.add(item.url)
            unique_by_url.append(item)

    logger.info(f"URL dedup: {len(news_items)} -> {len(unique_by_url)}")

    # Second pass: merge similar titles
    events: list[DeduplicatedEvent] = []

    for item in unique_by_url:
        # Check if similar to existing event
        merged = False
        for event in events:
            similarity = title_similarity(item.title, event.headline)
            if similarity >= similarity_threshold:
                # Merge into existing event
                if item.url not in event.source_urls:
                    event.source_urls.append(item.url)
                if item.site not in event.sources:
                    event.sources.append(item.site)
                for ticker in item.tickers:
                    if ticker not in event.tickers:
                        event.tickers.append(ticker)
                event.original_items.append(item)
                merged = True
                break

        if not merged:
            # Create new event
            events.append(
                DeduplicatedEvent(
                    headline=item.title,
                    text=item.text,
                    source_urls=[item.url],
                    sources=[item.site],
                    tickers=item.tickers.copy(),
                    published_date=item.published_date.isoformat(),
                    original_items=[item],
                )
            )

    logger.info(f"Title merge: {len(unique_by_url)} -> {len(events)}")

    return events


def filter_by_universe(
    events: list[DeduplicatedEvent],
    universe: set[str],
) -> list[DeduplicatedEvent]:
    """Filter events to only include those with tickers in universe.

    Args:
        events: List of events
        universe: Set of allowed tickers

    Returns:
        Filtered events
    """
    filtered = []
    for event in events:
        # Check if any ticker is in universe
        matching_tickers = [t for t in event.tickers if t in universe]
        if matching_tickers:
            # Update tickers to only include universe tickers
            event.tickers = matching_tickers
            filtered.append(event)

    logger.info(f"Universe filter: {len(events)} -> {len(filtered)}")
    return filtered
