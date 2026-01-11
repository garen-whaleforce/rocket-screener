"""Build Evidence Pack for Article 1 (Daily Brief).

Combines:
- Market snapshot from FMP
- Top events from scored/filtered news
- v2: Market thesis, quick hits, catalyst calendar, watchlist
"""

import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional

from app.evidence.schemas import (
    Article1Evidence,
    CatalystEvent,
    ImpactCard,
    MarketSnapshotItem,
    QuickHit,
    TopEvent,
    WatchlistItem,
)
from app.features.event_scoring import ScoredEvent
from app.ingest.fmp_client import FMPClient, MarketQuote

logger = logging.getLogger(__name__)


def strip_html(text: str) -> str:
    """Strip HTML tags from text.

    Removes <p>, <a>, <ul>, <li>, etc. and normalizes whitespace.
    """
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def remove_company_boilerplate(text: str) -> str:
    """Remove company encyclopedia/boilerplate sentences.

    Removes sentences like:
    - "X is a multinational conglomerate..."
    - "Company X is a leading provider of..."
    - "Founded in 1990, X is..."

    These add no value for news analysis.
    """
    if not text:
        return ""

    # Patterns for boilerplate sentences
    boilerplate_patterns = [
        r"^[A-Z][^.]*\s+is\s+a\s+(multinational|global|leading|major|premier|largest|world)[^.]*\.\s*",
        r"^[A-Z][^.]*\s+is\s+(headquartered|based)\s+(in|at)[^.]*\.\s*",
        r"^Founded\s+in\s+\d{4}[^.]*\.\s*",
        r"^[A-Z][^.]*\s+is\s+known\s+for[^.]*\.\s*",
        r"^[A-Z][^.]*\s+specializes\s+in[^.]*\.\s*",
        r"^The\s+company\s+(is|was|has\s+been)[^.]*\.\s*",
        r"^[A-Z][^.]*competing\s+with\s+other[^.]*\.\s*",
    ]

    for pattern in boilerplate_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    return text.strip()


def clean_what_happened(text: str, max_chars: int = 400) -> str:
    """Clean and truncate what_happened text.

    1. Strip HTML tags
    2. Remove company boilerplate
    3. Truncate to max_chars
    4. Ensure it ends with complete sentence

    Args:
        text: Raw text (may contain HTML)
        max_chars: Maximum characters to keep

    Returns:
        Clean, concise text
    """
    # Step 1: Strip HTML
    text = strip_html(text)

    # Step 2: Remove boilerplate
    text = remove_company_boilerplate(text)

    # Step 3: Truncate
    if len(text) > max_chars:
        text = text[:max_chars]
        # Try to end at sentence boundary
        last_period = text.rfind(".")
        if last_period > max_chars // 2:
            text = text[: last_period + 1]
        else:
            text = text.rsplit(" ", 1)[0] + "..."

    return text


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
            # 10Y yield uses bps display
            is_rate = symbol == "10Y"
            items.append(
                MarketSnapshotItem(
                    symbol=q.symbol,
                    name=q.name,
                    close=q.price,
                    change=q.change,
                    change_pct=q.change_percent,
                    is_rate=is_rate,
                )
            )

    return items


# ============================================================
# v2 Helper Functions
# ============================================================


def build_quick_reads(top_events: list[TopEvent]) -> list[str]:
    """Build formatted quick reads from top 3 events.

    Format: "📌 {headline} — {1-sentence summary}"
    """
    reads = []
    for event in top_events[:3]:
        # Use headline + shortened what_happened
        summary = event.what_happened[:80] if event.what_happened else ""
        if len(event.what_happened or "") > 80:
            summary = summary.rsplit(" ", 1)[0] + "..."
        reads.append(f"📌 {event.headline} — {summary}")
    return reads


def get_ticker_price_reactions(
    fmp_client: Optional[FMPClient],
    tickers: list[str],
) -> dict[str, str]:
    """Get price reactions for tickers.

    Returns dict of ticker -> formatted string like "+3.2%"
    """
    if not fmp_client or not tickers:
        return {}

    reactions = {}
    # Batch get quotes if possible
    unique_tickers = list(set(tickers))[:20]  # Limit to 20

    for ticker in unique_tickers:
        try:
            quote = fmp_client.get_quote(ticker)
            if quote:
                change_pct = quote.get("changesPercentage", 0) or 0
                # Format with sign
                sign = "+" if change_pct >= 0 else ""
                reactions[ticker] = f"{sign}{change_pct:.1f}%"
        except Exception as e:
            logger.debug(f"Failed to get quote for {ticker}: {e}")

    return reactions


def build_catalyst_calendar(
    fmp_client: Optional[FMPClient],
    target_date: date,
) -> tuple[list[CatalystEvent], list[CatalystEvent], list[CatalystEvent]]:
    """Build catalyst calendar for the date.

    Returns (econ_events, earnings_events, other_events)
    """
    econ_events: list[CatalystEvent] = []
    earnings_events: list[CatalystEvent] = []
    other_events: list[CatalystEvent] = []

    if not fmp_client:
        return econ_events, earnings_events, other_events

    # Get earnings calendar for today and tomorrow
    try:
        tomorrow = target_date + timedelta(days=1)
        earnings = fmp_client.get_earnings_calendar(target_date, tomorrow)

        for e in earnings[:15]:  # Limit to 15
            ticker = e.get("symbol", "")
            timing = "盤後" if e.get("time") == "amc" else "盤前"
            earnings_events.append(
                CatalystEvent(
                    time=timing,
                    event=f"{ticker} 財報",
                    ticker=ticker,
                    timing=timing,
                )
            )
    except Exception as e:
        logger.warning(f"Failed to get earnings calendar: {e}")

    # Static economic events (can be enhanced with real API later)
    # These are common recurring events
    weekday = target_date.weekday()
    if weekday == 3:  # Thursday
        econ_events.append(
            CatalystEvent(time="08:30 ET", event="初領失業金人數")
        )
    if weekday == 4:  # Friday
        if target_date.day <= 7:  # First Friday
            econ_events.append(
                CatalystEvent(time="08:30 ET", event="非農就業報告")
            )

    return econ_events, earnings_events, other_events


def build_watchlist(
    top_events: list[TopEvent],
    price_reactions: dict[str, str],
    fmp_client: Optional[FMPClient],
) -> list[WatchlistItem]:
    """Build watchlist from event tickers.

    Selects 3-7 tickers from events with key levels.
    """
    watchlist = []
    seen_tickers = set()

    for event in top_events:
        for ticker in event.tickers[:2]:  # Max 2 per event
            if ticker in seen_tickers:
                continue
            seen_tickers.add(ticker)

            # Get price data for key levels
            key_levels = "觀察中"
            if fmp_client:
                try:
                    quote = fmp_client.get_quote(ticker)
                    if quote:
                        price = quote.get("price", 0)
                        high_52w = quote.get("yearHigh", 0)
                        low_52w = quote.get("yearLow", 0)
                        if high_52w and low_52w:
                            support = price * 0.95
                            resistance = price * 1.05
                            key_levels = f"支撐 ${support:.0f} / 壓力 ${resistance:.0f}"
                except Exception:
                    pass

            change = price_reactions.get(ticker, "")
            reason = f"{event.headline[:30]}..."

            watchlist.append(
                WatchlistItem(
                    ticker=ticker,
                    reason=reason,
                    key_levels=key_levels,
                )
            )

            if len(watchlist) >= 7:
                break
        if len(watchlist) >= 7:
            break

    return watchlist


def build_quick_hits(
    fmp_client: Optional[FMPClient],
    top_event_urls: set[str],
    use_llm: bool = True,
) -> list[QuickHit]:
    """Build quick hits from additional news.

    Gets news not in top events and generates one-liner summaries.
    """
    if not fmp_client:
        return []

    from app.llm.client import get_llm_client

    quick_hits = []

    try:
        # Get latest news
        news_items = fmp_client.get_stock_news(limit=30)

        # Filter out news already in top events
        additional_news = [
            n for n in news_items if n.url not in top_event_urls
        ][:15]

        if not additional_news:
            return []

        if use_llm:
            llm_client = get_llm_client()
            if llm_client:
                # Prepare news for LLM
                news_data = [
                    {
                        "title": n.title,
                        "ticker": n.tickers[0] if n.tickers else "N/A",
                    }
                    for n in additional_news
                ]

                hits = llm_client.generate_quick_hits(news_data)
                for hit in hits[:15]:
                    quick_hits.append(
                        QuickHit(
                            summary=hit.get("summary", ""),
                            ticker=hit.get("ticker", ""),
                            change=hit.get("change"),
                        )
                    )
        else:
            # Fallback: use raw titles
            for n in additional_news[:10]:
                ticker = n.tickers[0] if n.tickers else ""
                quick_hits.append(
                    QuickHit(
                        summary=n.title[:50],
                        ticker=ticker,
                    )
                )

    except Exception as e:
        logger.warning(f"Failed to build quick hits: {e}")

    return quick_hits


def build_top_events(
    scored_events: list[ScoredEvent],
    price_changes: Optional[dict[str, float]] = None,
    price_reactions: Optional[dict[str, str]] = None,
    use_llm: bool = True,
) -> list[TopEvent]:
    """Build top events from scored events.

    Uses LLM to:
    1. Translate headline and what_happened to Traditional Chinese
    2. Fill in why_important, impact, next_watch
    3. v2: Generate impact_card (beneficiaries, losers, pricing_path, key_kpis)

    Falls back to English if LLM unavailable.
    """
    from app.llm.client import get_llm_client

    events = []
    llm_client = get_llm_client() if use_llm else None
    price_changes = price_changes or {}
    price_reactions = price_reactions or {}

    for i, scored in enumerate(scored_events, start=1):
        event = scored.event

        # Clean text: strip HTML, remove boilerplate, truncate
        text = clean_what_happened(event.text, max_chars=400)

        # Translate headline and what_happened to Traditional Chinese
        headline_zh = event.headline
        what_happened_zh = text

        if llm_client:
            try:
                translation = llm_client.translate_to_traditional_chinese(
                    headline=event.headline,
                    what_happened=text,
                )
                headline_zh = translation.get("headline_zh", event.headline)
                what_happened_zh = translation.get("what_happened_zh", text)
                logger.info(f"Translated event {i}: {headline_zh[:50]}...")
            except Exception as e:
                logger.warning(f"Translation failed for event {i}: {e}")

        # Generate analysis using LLM
        why_important = None
        impact = None
        next_watch = None

        if llm_client:
            try:
                analysis = llm_client.generate_event_analysis(
                    headline=headline_zh,
                    what_happened=what_happened_zh,
                    related_tickers=event.tickers,
                    price_changes=price_changes,
                )
                why_important = analysis.get("why_important")
                impact = analysis.get("impact")
                next_watch = analysis.get("next_watch")
                logger.info(f"LLM generated analysis for event {i}: {headline_zh[:50]}...")
            except Exception as e:
                logger.warning(f"LLM analysis failed for event {i}: {e}")

        # v2: Build price_reaction string
        price_reaction = None
        if event.tickers and price_reactions:
            reactions = []
            for ticker in event.tickers[:2]:
                if ticker in price_reactions:
                    reactions.append(f"{ticker} {price_reactions[ticker]}")
            if reactions:
                price_reaction = " / ".join(reactions)

        # v2: Generate impact_card
        impact_card = None
        if llm_client and i <= 3:  # Only for top 3 events
            try:
                card_data = llm_client.generate_impact_card(
                    headline=headline_zh,
                    what_happened=what_happened_zh,
                    related_tickers=event.tickers,
                )
                impact_card = ImpactCard(
                    beneficiaries=card_data.get("beneficiaries", ""),
                    losers=card_data.get("losers", ""),
                    pricing_path=card_data.get("pricing_path", ""),
                    key_kpis=card_data.get("key_kpis", ""),
                )
                logger.info(f"Generated impact card for event {i}")
            except Exception as e:
                logger.warning(f"Impact card generation failed for event {i}: {e}")

        events.append(
            TopEvent(
                rank=i,
                tickers=event.tickers,
                event_type=scored.event_type,
                headline=headline_zh,
                what_happened=what_happened_zh,
                why_important=why_important,
                impact=impact,
                next_watch=next_watch,
                source_urls=event.source_urls,
                # v2 fields
                price_reaction=price_reaction,
                impact_card=impact_card,
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
    price_changes: Optional[dict[str, float]] = None,
    use_llm: bool = True,
) -> Article1Evidence:
    """Build complete Article 1 Evidence Pack.

    Args:
        target_date: Date for the article
        fmp_client: FMP client (None for dry-run without API)
        scored_events: Scored and filtered events
        price_changes: Dict of ticker -> price change % for LLM context
        use_llm: Whether to use LLM for generating analysis

    Returns:
        Article1Evidence ready for LLM/template rendering
    """
    from app.llm.client import get_llm_client

    # Get market snapshot
    market_data_timestamp = None
    if fmp_client:
        try:
            quotes = fmp_client.get_market_snapshot()
            market_snapshot = build_market_snapshot(quotes)
            market_data_timestamp = datetime.now().strftime("%Y/%m/%d %H:%M ET")
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

    # v2: Get price reactions for all event tickers
    all_tickers = []
    for scored in scored_events:
        all_tickers.extend(scored.event.tickers)
    price_reactions = get_ticker_price_reactions(fmp_client, all_tickers)

    # Build top events with LLM analysis (including v2 fields)
    top_events = build_top_events(
        scored_events, price_changes, price_reactions, use_llm
    )

    # Generate watch tonight
    watch_tonight = generate_watch_tonight(top_events, market_snapshot)

    # v2: Generate market thesis
    market_thesis = None
    if use_llm and market_snapshot and top_events:
        llm_client = get_llm_client()
        if llm_client:
            try:
                # Prepare data for LLM
                snapshot_data = [
                    {"symbol": m.symbol, "change_pct": m.change_pct}
                    for m in market_snapshot
                ]
                event_headlines = [e.headline for e in top_events[:5]]
                market_thesis = llm_client.generate_market_thesis(
                    snapshot_data, event_headlines
                )
                logger.info(f"Generated market thesis: {market_thesis[:50]}...")
            except Exception as e:
                logger.warning(f"Failed to generate market thesis: {e}")

    # v2: Build quick reads
    quick_reads = build_quick_reads(top_events)

    # v2: Build catalyst calendar
    catalyst_econ, catalyst_earnings, catalyst_other = build_catalyst_calendar(
        fmp_client, target_date
    )

    # v2: Build watchlist
    watchlist = build_watchlist(top_events, price_reactions, fmp_client)

    # v2: Build quick hits from additional news
    top_event_urls = set()
    for scored in scored_events:
        top_event_urls.update(scored.event.source_urls)
    quick_hits = build_quick_hits(fmp_client, top_event_urls, use_llm)

    return Article1Evidence(
        date=target_date,
        market_snapshot=market_snapshot,
        top_events=top_events,
        watch_tonight=watch_tonight,
        # v2 fields
        market_thesis=market_thesis,
        quick_reads=quick_reads,
        quick_hits=quick_hits,
        catalyst_econ=catalyst_econ,
        catalyst_earnings=catalyst_earnings,
        catalyst_other=catalyst_other,
        watchlist=watchlist,
        market_data_timestamp=market_data_timestamp,
    )
