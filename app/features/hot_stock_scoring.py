"""Hot stock scoring for article 2 selection.

Scores stocks based on:
- Price/volume shock (from quotes/movers)
- News mentions (from news count)
- Data completeness (financials/valuation available)
- Recent events (earnings, product launches)
- Trading activity (most actives)

Candidate pool sources:
1. News top mentions (tickers with most news)
2. Most active stocks (volume leaders)
3. Gainers/losers (price movers)

Optimizations (v2):
- Parallel API calls using ThreadPoolExecutor
- In-memory session cache for company data
- Batch data fetching
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional
import threading

from app.ingest.fmp_client import FMPClient

logger = logging.getLogger(__name__)

# Thread-safe cache for company data (session-level)
_cache_lock = threading.Lock()
_company_cache: dict[str, dict] = {}


# Priority tickers (mega caps that should always be considered if mentioned)
PRIORITY_TICKERS = {
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA",
    "AMD", "INTC", "CRM", "ADBE", "NFLX", "JPM", "V", "MA",
}

# Max concurrent API calls
MAX_WORKERS = 8


def clear_cache():
    """Clear the company data cache."""
    global _company_cache
    with _cache_lock:
        _company_cache.clear()
    logger.debug("Company cache cleared")


def _fetch_company_data(fmp_client: FMPClient, ticker: str) -> dict:
    """Fetch all company data for a ticker (with caching).

    Returns:
        Dict with profile, ratios, income, and completeness score
    """
    # Check cache first
    with _cache_lock:
        if ticker in _company_cache:
            return _company_cache[ticker]

    # Fetch data
    result = {
        "ticker": ticker,
        "profile": None,
        "ratios": None,
        "income": None,
        "completeness": 0.0,
        "name": ticker,
    }

    try:
        result["profile"] = fmp_client.get_company_profile(ticker)
        if result["profile"]:
            result["name"] = result["profile"].get("companyName", ticker)
    except Exception as e:
        logger.debug(f"Failed to get profile for {ticker}: {e}")

    try:
        result["ratios"] = fmp_client.get_financial_ratios(ticker)
    except Exception as e:
        logger.debug(f"Failed to get ratios for {ticker}: {e}")

    try:
        income = fmp_client.get_income_statement(ticker, limit=1)
        result["income"] = income if income else None
    except Exception as e:
        logger.debug(f"Failed to get income for {ticker}: {e}")

    # Calculate completeness
    has_profile = result["profile"] is not None
    has_ratios = result["ratios"] is not None
    has_income = result["income"] is not None and len(result["income"]) > 0
    result["completeness"] = sum([has_profile, has_ratios, has_income]) / 3.0

    # Store in cache
    with _cache_lock:
        _company_cache[ticker] = result

    return result


def _fetch_all_company_data(
    fmp_client: FMPClient,
    tickers: list[str],
) -> dict[str, dict]:
    """Fetch company data for multiple tickers in parallel.

    Args:
        fmp_client: FMP API client
        tickers: List of tickers to fetch

    Returns:
        Dict of ticker -> company data
    """
    results = {}

    logger.info(f"Fetching data for {len(tickers)} tickers (parallel, {MAX_WORKERS} workers)")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all fetch tasks
        future_to_ticker = {
            executor.submit(_fetch_company_data, fmp_client, ticker): ticker
            for ticker in tickers
        }

        # Collect results as they complete
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                data = future.result()
                results[ticker] = data
            except Exception as e:
                logger.warning(f"Failed to fetch data for {ticker}: {e}")
                results[ticker] = {
                    "ticker": ticker,
                    "completeness": 0.0,
                    "name": ticker,
                }

    logger.info(f"Fetched data for {len(results)} tickers")
    return results


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
    source: str = ""  # Where this candidate came from


def _get_candidate_tickers(
    fmp_client: FMPClient,
    universe: set[str],
    news_ticker_counts: dict[str, int],
    top_news_count: int = 15,
    top_actives_count: int = 10,
) -> dict[str, dict]:
    """Build candidate ticker pool from multiple sources.

    Sources:
    1. News top mentions (tickers with most news)
    2. Most active stocks (volume leaders)
    3. Gainers/losers (price movers)

    Args:
        fmp_client: FMP API client
        universe: Set of allowed tickers
        news_ticker_counts: Dict of ticker -> news mention count
        top_news_count: How many top news tickers to include
        top_actives_count: How many actives to include

    Returns:
        Dict of ticker -> {source, price_change, ...}
    """
    candidates = {}

    # Source 1: Top news mentions (most important source)
    sorted_news = sorted(
        [(t, c) for t, c in news_ticker_counts.items() if t in universe],
        key=lambda x: x[1],
        reverse=True,
    )
    for ticker, count in sorted_news[:top_news_count]:
        if count >= 1:  # At least 1 mention
            candidates[ticker] = {
                "source": "news",
                "news_count": count,
                "price_change": 0,
            }
            logger.debug(f"News candidate: {ticker} ({count} mentions)")

    # Source 2: Most active stocks
    try:
        actives = fmp_client.get_most_active()
        for item in actives[:top_actives_count]:
            ticker = item.get("symbol", "")
            if ticker in universe and ticker not in candidates:
                candidates[ticker] = {
                    "source": "actives",
                    "news_count": news_ticker_counts.get(ticker, 0),
                    "price_change": item.get("changesPercentage", 0),
                }
                logger.debug(f"Active candidate: {ticker}")
    except Exception as e:
        logger.warning(f"Failed to get actives: {e}")

    # Source 3: Gainers/losers
    try:
        movers = fmp_client.get_gainers_losers()
        all_movers = movers.get("gainers", [])[:10] + movers.get("losers", [])[:10]
        for item in all_movers:
            ticker = item.get("symbol", "")
            if ticker in universe:
                change_pct = item.get("changesPercentage", 0)
                if ticker in candidates:
                    # Update price change if from movers
                    candidates[ticker]["price_change"] = change_pct
                else:
                    candidates[ticker] = {
                        "source": "movers",
                        "news_count": news_ticker_counts.get(ticker, 0),
                        "price_change": change_pct,
                    }
                    logger.debug(f"Mover candidate: {ticker} ({change_pct:+.1f}%)")
    except Exception as e:
        logger.warning(f"Failed to get movers: {e}")

    # Always include priority tickers if they have news
    for ticker in PRIORITY_TICKERS:
        if ticker in universe and ticker not in candidates:
            news_count = news_ticker_counts.get(ticker, 0)
            if news_count >= 1:
                candidates[ticker] = {
                    "source": "priority",
                    "news_count": news_count,
                    "price_change": 0,
                }
                logger.debug(f"Priority candidate: {ticker} ({news_count} mentions)")

    logger.info(f"Built candidate pool: {len(candidates)} tickers")
    return candidates


def score_hot_stocks(
    fmp_client: FMPClient,
    universe: set[str],
    news_ticker_counts: dict[str, int],
    limit: int = 10,
) -> list[HotStockCandidate]:
    """Score and rank stocks for deep dive selection.

    Candidate pool comes from 3 sources:
    1. News top mentions (tickers with most news)
    2. Most active stocks (volume leaders)
    3. Gainers/losers (price movers)

    Args:
        fmp_client: FMP API client
        universe: Set of allowed tickers
        news_ticker_counts: Dict of ticker -> news mention count
        limit: Maximum candidates to return

    Returns:
        List of hot stock candidates, sorted by score
    """
    # Build candidate pool from multiple sources
    candidate_pool = _get_candidate_tickers(
        fmp_client, universe, news_ticker_counts
    )

    if not candidate_pool:
        logger.warning("No candidates found in pool")
        return []

    # Fetch all company data in parallel (OPTIMIZATION)
    tickers_to_fetch = list(candidate_pool.keys())
    company_data = _fetch_all_company_data(fmp_client, tickers_to_fetch)

    candidates = []

    for ticker, info in candidate_pool.items():
        news_count = info.get("news_count", 0)
        price_change = info.get("price_change", 0)
        source = info.get("source", "unknown")

        # Price move score (0-35)
        abs_change = abs(price_change)
        if abs_change >= 10:
            price_score = 35
        elif abs_change >= 5:
            price_score = 28
        elif abs_change >= 3:
            price_score = 20
        elif abs_change >= 2:
            price_score = 12
        elif abs_change >= 1:
            price_score = 5
        else:
            price_score = 0

        # News score (0-35) - more weight on news
        if news_count >= 5:
            news_score = 35
        elif news_count >= 3:
            news_score = 28
        elif news_count >= 2:
            news_score = 20
        elif news_count >= 1:
            news_score = 12
        else:
            news_score = 0

        # Get pre-fetched company data
        data = company_data.get(ticker, {})
        data_completeness = data.get("completeness", 0.0)
        name = data.get("name", ticker)
        data_score = int(data_completeness * 30)

        # Skip if no financial data
        if data_completeness < 0.3:
            logger.debug(f"Skipping {ticker}: insufficient data ({data_completeness:.0%})")
            continue

        total_score = price_score + news_score + data_score

        # Bonus for priority tickers
        if ticker in PRIORITY_TICKERS:
            total_score += 5

        # Determine reason
        if abs_change >= 5:
            reason = f"股價大幅波動 {price_change:+.1f}%"
        elif news_count >= 3:
            reason = f"新聞熱度高（{news_count} 則報導）"
        elif source == "actives":
            reason = "交易量異常活躍"
        else:
            reason = "市場關注度上升"

        candidates.append(
            HotStockCandidate(
                ticker=ticker,
                name=name,
                score=total_score,
                price_change_pct=price_change,
                news_count=news_count,
                has_recent_earnings=False,
                data_completeness=data_completeness,
                reason=reason,
                source=source,
            )
        )

    # Sort by score
    candidates.sort(key=lambda x: x.score, reverse=True)

    logger.info(f"Scored {len(candidates)} candidates, returning top {limit}")
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
