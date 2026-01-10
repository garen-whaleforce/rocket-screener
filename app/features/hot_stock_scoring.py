"""Hot stock scoring for article 2 selection.

Scores stocks based on:
- Price/volume shock (from quotes/movers)
- News mentions (from news count)
- Data completeness (financials/valuation available)
- Recent events (earnings, product launches)
"""

import logging
from dataclasses import dataclass
from typing import Optional

from app.ingest.fmp_client import FMPClient

logger = logging.getLogger(__name__)


@dataclass
class HotStockCandidate:
    """Candidate stock for deep dive analysis."""

    ticker: str
    name: str
    score: float
    price_change_pct: float
    news_count: int
    has_recent_earnings: bool
    data_completeness: float  # 0-1
    reason: str  # Why this stock is hot


def score_hot_stocks(
    fmp_client: FMPClient,
    universe: set[str],
    news_ticker_counts: dict[str, int],
    limit: int = 10,
) -> list[HotStockCandidate]:
    """Score and rank stocks for deep dive selection.

    Args:
        fmp_client: FMP API client
        universe: Set of allowed tickers
        news_ticker_counts: Dict of ticker -> news mention count
        limit: Maximum candidates to return

    Returns:
        List of hot stock candidates, sorted by score
    """
    candidates = []

    # Get movers
    movers = fmp_client.get_gainers_losers()
    all_movers = movers.get("gainers", []) + movers.get("losers", [])

    # Filter to universe and score
    for mover in all_movers:
        ticker = mover.get("symbol", "")
        if ticker not in universe:
            continue

        change_pct = abs(mover.get("changesPercentage", 0))
        news_count = news_ticker_counts.get(ticker, 0)

        # Price move score (0-40)
        if change_pct >= 10:
            price_score = 40
        elif change_pct >= 5:
            price_score = 30
        elif change_pct >= 3:
            price_score = 20
        elif change_pct >= 2:
            price_score = 10
        else:
            price_score = 5

        # News score (0-30)
        if news_count >= 5:
            news_score = 30
        elif news_count >= 3:
            news_score = 20
        elif news_count >= 1:
            news_score = 10
        else:
            news_score = 0

        # Check data completeness
        try:
            profile = fmp_client.get_company_profile(ticker)
            ratios = fmp_client.get_financial_ratios(ticker)
            data_score = 30 if (profile and ratios) else 15
            data_completeness = 1.0 if (profile and ratios) else 0.5
            name = profile.get("companyName", ticker) if profile else ticker
        except Exception:
            data_score = 0
            data_completeness = 0
            name = ticker

        total_score = price_score + news_score + data_score

        # Determine reason
        if change_pct >= 5:
            reason = f"股價大幅波動 {mover.get('changesPercentage', 0):+.1f}%"
        elif news_count >= 3:
            reason = f"新聞熱度高（{news_count} 則報導）"
        else:
            reason = "市場關注度上升"

        candidates.append(
            HotStockCandidate(
                ticker=ticker,
                name=name,
                score=total_score,
                price_change_pct=mover.get("changesPercentage", 0),
                news_count=news_count,
                has_recent_earnings=False,  # Will check in v5
                data_completeness=data_completeness,
                reason=reason,
            )
        )

    # Sort by score
    candidates.sort(key=lambda x: x.score, reverse=True)

    return candidates[:limit]


def select_hot_stock(candidates: list[HotStockCandidate]) -> Optional[HotStockCandidate]:
    """Select the best hot stock for today's deep dive.

    Prefers stocks with:
    1. High score
    2. Good data completeness
    3. Clear catalyst/reason
    """
    if not candidates:
        return None

    # Filter for good data completeness
    good_data = [c for c in candidates if c.data_completeness >= 0.8]

    if good_data:
        return good_data[0]

    # Fallback to best overall
    return candidates[0]
