"""Build Evidence Pack for Article 1 (Daily Brief).

Combines:
- Market snapshot from FMP
- Top events from scored/filtered news
"""

import logging
from datetime import date
from typing import Optional

from app.evidence.schemas import (
    Article1Evidence,
    MarketSnapshotItem,
    TopEvent,
)
from app.features.event_scoring import ScoredEvent
from app.ingest.fmp_client import FMPClient, MarketQuote

logger = logging.getLogger(__name__)


def build_market_snapshot(
    quotes: dict[str, MarketQuote],
) -> list[MarketSnapshotItem]:
    """Build market snapshot items from quotes.

    Order: SPY, QQQ, DIA, 10Y, DXY, Oil, Gold, BTC
    """
    # Desired order
    order = ["SPY", "QQQ", "DIA", "10Y", "DXY", "Oil", "Gold", "BTC"]

    items = []
    for symbol in order:
        if symbol in quotes:
            q = quotes[symbol]
            items.append(
                MarketSnapshotItem(
                    symbol=q.symbol,
                    name=q.name,
                    close=q.price,
                    change=q.change,
                    change_pct=q.change_percent,
                )
            )

    return items


def build_top_events(
    scored_events: list[ScoredEvent],
) -> list[TopEvent]:
    """Build top events from scored events.

    Note: LLM will later fill in why_important, impact, next_watch.
    For now, we use the text from the news item.
    """
    events = []

    for i, scored in enumerate(scored_events, start=1):
        event = scored.event

        # Truncate text for what_happened
        text = event.text
        if len(text) > 500:
            text = text[:500] + "..."

        events.append(
            TopEvent(
                rank=i,
                tickers=event.tickers,
                event_type=scored.event_type,
                headline=event.headline,
                what_happened=text,
                source_urls=event.source_urls,
            )
        )

    return events


def generate_watch_tonight(
    top_events: list[TopEvent],
    market_snapshot: list[MarketSnapshotItem],
) -> list[str]:
    """Generate "watch tonight" items based on events.

    This is a simple heuristic. LLM will refine later.
    """
    items = []

    # Check for earnings-related events
    earnings_tickers = []
    for event in top_events:
        if event.event_type == "earnings":
            earnings_tickers.extend(event.tickers)

    if earnings_tickers:
        items.append(f"持續關注 {', '.join(earnings_tickers[:3])} 財報後續反應")

    # Check for macro events
    has_macro = any(e.event_type == "macro" for e in top_events)
    if has_macro:
        items.append("Fed 官員談話與經濟數據更新")

    # Default items
    if not items:
        items = [
            "盤後財報公布動態",
            "亞洲市場開盤反應",
            "重要經濟數據公布",
        ]

    return items[:5]


def build_article1_evidence(
    target_date: date,
    fmp_client: Optional[FMPClient],
    scored_events: list[ScoredEvent],
) -> Article1Evidence:
    """Build complete Article 1 Evidence Pack.

    Args:
        target_date: Date for the article
        fmp_client: FMP client (None for dry-run without API)
        scored_events: Scored and filtered events

    Returns:
        Article1Evidence ready for LLM/template rendering
    """
    # Get market snapshot
    if fmp_client:
        try:
            quotes = fmp_client.get_market_snapshot()
            market_snapshot = build_market_snapshot(quotes)
        except Exception as e:
            logger.error(f"Failed to get market snapshot: {e}")
            market_snapshot = []
    else:
        # Placeholder for dry-run
        market_snapshot = [
            MarketSnapshotItem(
                symbol="SPY", name="S&P 500 ETF", close=0, change=0, change_pct=0
            ),
            MarketSnapshotItem(
                symbol="QQQ", name="Nasdaq 100 ETF", close=0, change=0, change_pct=0
            ),
        ]

    # Build top events
    top_events = build_top_events(scored_events)

    # Generate watch tonight
    watch_tonight = generate_watch_tonight(top_events, market_snapshot)

    return Article1Evidence(
        date=target_date,
        market_snapshot=market_snapshot,
        top_events=top_events,
        watch_tonight=watch_tonight,
    )
