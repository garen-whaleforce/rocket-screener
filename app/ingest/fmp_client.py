"""FMP (Financial Modeling Prep) API client.

Handles all data ingestion from FMP API using STABLE endpoints only.
Reference: FMP_STABLE_API_REFERENCE.md

IMPORTANT: Only use /stable/ endpoints. Never use /api/v3 or /api/v4.

Optimizations (v2):
- Session-level caching for company data
- Cache TTL for frequently accessed data
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from functools import wraps
from typing import Any, Optional

import requests

from app.config import FMPConfig

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_TTL_SECONDS = 300  # 5 minutes
_cache_lock = threading.Lock()
_cache: dict[str, tuple[Any, float]] = {}  # key -> (value, timestamp)


def clear_fmp_cache():
    """Clear the FMP data cache."""
    global _cache
    with _cache_lock:
        _cache.clear()
    logger.debug("FMP cache cleared")


def _cache_key(method_name: str, *args, **kwargs) -> str:
    """Generate cache key from method name and arguments."""
    key_parts = [method_name]
    key_parts.extend(str(a) for a in args)
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return ":".join(key_parts)


def cached(ttl: int = CACHE_TTL_SECONDS):
    """Decorator to cache method results.

    Args:
        ttl: Time to live in seconds (default: 5 minutes)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            key = _cache_key(func.__name__, *args, **kwargs)

            # Check cache
            with _cache_lock:
                if key in _cache:
                    value, timestamp = _cache[key]
                    if time.time() - timestamp < ttl:
                        logger.debug(f"Cache hit: {key}")
                        return value

            # Call function
            result = func(self, *args, **kwargs)

            # Store in cache
            with _cache_lock:
                _cache[key] = (result, time.time())

            return result
        return wrapper
    return decorator


@dataclass
class MarketQuote:
    """Market quote data."""

    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    timestamp: Optional[datetime] = None


@dataclass
class NewsItem:
    """News item from FMP."""

    title: str
    text: str
    url: str
    site: str
    published_date: datetime
    tickers: list[str]
    image_url: Optional[str] = None


class FMPClient:
    """Client for FMP API using stable endpoints.

    All endpoints use /stable/ prefix as per FMP_STABLE_API_REFERENCE.md.
    """

    def __init__(self, config: FMPConfig):
        self.config = config
        self.base_url = config.base_url.rstrip("/")

    def _request(
        self, endpoint: str, params: Optional[dict] = None
    ) -> Any:
        """Make API request to stable endpoint.

        Args:
            endpoint: Endpoint path (without /stable/ prefix)
            params: Query parameters

        Returns:
            JSON response
        """
        # Ensure we use stable endpoint
        if not endpoint.startswith("stable/"):
            endpoint = f"stable/{endpoint}"

        url = f"{self.base_url}/{endpoint}"
        all_params = {"apikey": self.config.api_key}
        if params:
            all_params.update(params)

        logger.debug(f"FMP request: {endpoint}")
        response = requests.get(url, params=all_params, timeout=30)
        response.raise_for_status()

        return response.json()

    def _calc_change_pct(self, price: float, change: float) -> float:
        """Calculate change percentage from price and change.

        Always calculates ourselves instead of trusting API changesPercentage.
        """
        if price == 0 or change == 0:
            return 0.0
        prev_price = price - change
        if prev_price == 0:
            return 0.0
        return round((change / prev_price) * 100, 2)

    def get_market_snapshot(self) -> dict[str, MarketQuote]:
        """Get market snapshot for key indices and assets.

        Uses:
        - /stable/batch-quote for ETFs
        - /stable/batch-crypto-quotes for BTC
        - /stable/batch-commodity-quotes for Gold/Oil
        - /stable/treasury-rates for 10Y yield

        NOTE: We calculate change_percent ourselves to avoid API inconsistencies.
        """
        quotes = {}

        # Get ETF quotes (SPY, QQQ, DIA)
        try:
            data = self._request("batch-quote", {"symbols": "SPY,QQQ,DIA"})
            symbols_map = {
                "SPY": "S&P 500 ETF",
                "QQQ": "Nasdaq 100 ETF",
                "DIA": "道瓊工業 ETF",
            }
            for item in data or []:
                symbol = item.get("symbol", "")
                if symbol in symbols_map:
                    price = item.get("price", 0) or 0
                    change = item.get("change", 0) or 0
                    # Calculate percentage ourselves - don't trust API changesPercentage
                    change_pct = self._calc_change_pct(price, change)
                    quotes[symbol] = MarketQuote(
                        symbol=symbol,
                        name=symbols_map[symbol],
                        price=price,
                        change=change,
                        change_percent=change_pct,
                    )
        except Exception as e:
            logger.warning(f"Failed to get ETF quotes: {e}")

        # Get crypto (Bitcoin) using batch-crypto-quotes
        try:
            data = self._request("batch-crypto-quotes")
            for item in data or []:
                if item.get("symbol") == "BTCUSD":
                    price = item.get("price", 0) or 0
                    change = item.get("change", 0) or 0
                    quotes["BTC"] = MarketQuote(
                        symbol="BTC",
                        name="Bitcoin",
                        price=price,
                        change=change,
                        change_percent=self._calc_change_pct(price, change),
                    )
                    break
        except Exception as e:
            logger.warning(f"Failed to get BTC quote: {e}")

        # Get commodities using batch-commodity-quotes
        try:
            data = self._request("batch-commodity-quotes")
            for item in data or []:
                symbol = item.get("symbol", "")
                price = item.get("price", 0) or 0
                change = item.get("change", 0) or 0
                change_pct = self._calc_change_pct(price, change)
                if "GC" in symbol or symbol == "GCUSD":
                    quotes["Gold"] = MarketQuote(
                        symbol="Gold",
                        name="黃金",
                        price=price,
                        change=change,
                        change_percent=change_pct,
                    )
                elif "CL" in symbol or symbol == "CLUSD":
                    quotes["Oil"] = MarketQuote(
                        symbol="Oil",
                        name="原油 (WTI)",
                        price=price,
                        change=change,
                        change_percent=change_pct,
                    )
        except Exception as e:
            logger.warning(f"Failed to get commodity quotes: {e}")

        # Get treasury yield using treasury-rates
        try:
            data = self._request("treasury-rates")
            if data and len(data) > 0:
                latest = data[0]
                quotes["10Y"] = MarketQuote(
                    symbol="10Y",
                    name="10Y 殖利率",
                    price=latest.get("year10", 0),
                    change=0,
                    change_percent=0,
                )
        except Exception as e:
            logger.warning(f"Failed to get treasury: {e}")

        return quotes

    def get_stock_news(
        self,
        tickers: Optional[list[str]] = None,
        limit: int = 50,
    ) -> list[NewsItem]:
        """Get stock news.

        Uses: /stable/news/stock-latest or /stable/news/stock?symbols=

        Args:
            tickers: Optional list of tickers to filter by
            limit: Maximum number of news items

        Returns:
            List of news items
        """
        try:
            if tickers:
                # Use symbol-specific endpoint
                data = self._request(
                    "news/stock",
                    {"symbols": ",".join(tickers), "page": 0, "limit": limit}
                )
            else:
                # Use latest news endpoint
                data = self._request(
                    "news/stock-latest",
                    {"page": 0, "limit": limit}
                )
        except Exception as e:
            logger.error(f"Failed to get stock news: {e}")
            return []

        return self._parse_news_items(data or [])

    def get_general_news(self, limit: int = 30) -> list[NewsItem]:
        """Get general market news.

        Uses: /stable/fmp-articles
        """
        try:
            data = self._request("fmp-articles", {"page": 0, "limit": limit})
        except Exception as e:
            logger.error(f"Failed to get general news: {e}")
            return []

        news_items = []
        content = data.get("content", []) if isinstance(data, dict) else data
        for item in content or []:
            try:
                pub_date_str = item.get("date", "")
                try:
                    pub_date = datetime.fromisoformat(
                        pub_date_str.replace("Z", "+00:00")
                    )
                except ValueError:
                    pub_date = datetime.now()

                news_items.append(
                    NewsItem(
                        title=item.get("title", ""),
                        text=item.get("content", ""),
                        url=item.get("link", ""),
                        site="FMP",
                        published_date=pub_date,
                        tickers=item.get("tickers", []) or [],
                        image_url=item.get("image"),
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to parse general news item: {e}")
                continue

        return news_items

    def _parse_news_items(self, data: list) -> list[NewsItem]:
        """Parse news items from API response."""
        news_items = []
        for item in data:
            try:
                pub_date_str = item.get("publishedDate", "") or ""
                try:
                    pub_date = datetime.fromisoformat(
                        pub_date_str.replace("Z", "+00:00")
                    )
                except ValueError:
                    pub_date = datetime.now()

                # Handle None or missing symbol field
                ticker_str = item.get("symbol") or ""
                item_tickers = [t.strip() for t in ticker_str.split(",") if t.strip()]

                news_items.append(
                    NewsItem(
                        title=item.get("title", "") or "",
                        text=item.get("text", "") or "",
                        url=item.get("url", "") or "",
                        site=item.get("site", "") or "",
                        published_date=pub_date,
                        tickers=item_tickers,
                        image_url=item.get("image"),
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to parse news item: {e}")
                continue

        return news_items

    @cached(ttl=60)  # 1 minute cache for quotes
    def get_quote(self, symbol: str) -> Optional[dict]:
        """Get quote for a single symbol.

        Uses: /stable/quote?symbol=
        """
        try:
            data = self._request("quote", {"symbol": symbol})
            return data[0] if data else None
        except Exception as e:
            logger.error(f"Failed to get quote for {symbol}: {e}")
            return None

    @cached(ttl=3600)  # 1 hour cache for profiles (rarely change)
    def get_company_profile(self, symbol: str) -> Optional[dict]:
        """Get company profile.

        Uses: /stable/profile?symbol=
        """
        try:
            data = self._request("profile", {"symbol": symbol})
            return data[0] if data else None
        except Exception as e:
            logger.error(f"Failed to get profile for {symbol}: {e}")
            return None

    @cached(ttl=3600)  # 1 hour cache for ratios
    def get_financial_ratios(self, symbol: str) -> Optional[dict]:
        """Get financial ratios (TTM).

        Uses: /stable/ratios-ttm?symbol=
        """
        try:
            data = self._request("ratios-ttm", {"symbol": symbol})
            return data[0] if data else None
        except Exception as e:
            logger.error(f"Failed to get ratios for {symbol}: {e}")
            return None

    @cached(ttl=3600)  # 1 hour cache for metrics
    def get_key_metrics(self, symbol: str) -> Optional[dict]:
        """Get key metrics (TTM).

        Uses: /stable/key-metrics-ttm?symbol=
        """
        try:
            data = self._request("key-metrics-ttm", {"symbol": symbol})
            return data[0] if data else None
        except Exception as e:
            logger.error(f"Failed to get metrics for {symbol}: {e}")
            return None

    def get_income_statement(
        self, symbol: str, period: str = "quarter", limit: int = 4
    ) -> list[dict]:
        """Get income statements.

        Uses: /stable/income-statement?symbol=&period=
        """
        try:
            data = self._request(
                "income-statement",
                {"symbol": symbol, "period": period, "limit": limit},
            )
            return data or []
        except Exception as e:
            logger.error(f"Failed to get income statement for {symbol}: {e}")
            return []

    def get_balance_sheet(
        self, symbol: str, period: str = "quarter", limit: int = 4
    ) -> list[dict]:
        """Get balance sheet statements.

        Uses: /stable/balance-sheet-statement?symbol=&period=
        """
        try:
            data = self._request(
                "balance-sheet-statement",
                {"symbol": symbol, "period": period, "limit": limit},
            )
            return data or []
        except Exception as e:
            logger.error(f"Failed to get balance sheet for {symbol}: {e}")
            return []

    def get_cash_flow(
        self, symbol: str, period: str = "quarter", limit: int = 4
    ) -> list[dict]:
        """Get cash flow statements.

        Uses: /stable/cash-flow-statement?symbol=&period=
        """
        try:
            data = self._request(
                "cash-flow-statement",
                {"symbol": symbol, "period": period, "limit": limit},
            )
            return data or []
        except Exception as e:
            logger.error(f"Failed to get cash flow for {symbol}: {e}")
            return []

    def get_stock_peers(self, symbol: str) -> list[str]:
        """Get stock peers/competitors.

        Uses: /stable/stock-peers?symbol=

        Returns symbols of peer companies (extracts from full company info).
        """
        try:
            data = self._request("stock-peers", {"symbol": symbol})
            if not data:
                return []

            # FMP returns list of company info dicts with 'symbol' key
            # Extract just the symbols, excluding the target symbol itself
            peers = []
            for item in data:
                peer_symbol = item.get("symbol")
                if peer_symbol and peer_symbol != symbol:
                    peers.append(peer_symbol)

            return peers[:10]  # Limit to 10 peers
        except Exception as e:
            logger.error(f"Failed to get peers for {symbol}: {e}")
            return []

    def get_gainers_losers(self) -> dict[str, list[dict]]:
        """Get market gainers and losers.

        Uses: /stable/biggest-gainers and /stable/biggest-losers
        """
        result = {"gainers": [], "losers": []}

        try:
            gainers = self._request("biggest-gainers")
            result["gainers"] = gainers[:10] if gainers else []
        except Exception as e:
            logger.warning(f"Failed to get gainers: {e}")

        try:
            losers = self._request("biggest-losers")
            result["losers"] = losers[:10] if losers else []
        except Exception as e:
            logger.warning(f"Failed to get losers: {e}")

        return result

    def get_sp500_constituents(self) -> list[str]:
        """Get S&P 500 constituent symbols.

        Uses: /stable/sp500-constituent
        """
        try:
            data = self._request("sp500-constituent")
            return [item["symbol"] for item in data] if data else []
        except Exception as e:
            logger.error(f"Failed to get S&P 500 constituents: {e}")
            return []

    def get_earnings_calendar(
        self, from_date: Optional[date] = None, to_date: Optional[date] = None
    ) -> list[dict]:
        """Get earnings calendar.

        Uses: /stable/earnings-calendar
        """
        params = {}
        if from_date:
            params["from"] = from_date.isoformat()
        if to_date:
            params["to"] = to_date.isoformat()

        try:
            data = self._request("earnings-calendar", params if params else None)
            return data or []
        except Exception as e:
            logger.error(f"Failed to get earnings calendar: {e}")
            return []

    def get_analyst_estimates(
        self, symbol: str, period: str = "quarter", limit: int = 4
    ) -> list[dict]:
        """Get analyst estimates.

        Uses: /stable/analyst-estimates?symbol=
        """
        try:
            data = self._request(
                "analyst-estimates",
                {"symbol": symbol, "period": period, "limit": limit}
            )
            return data or []
        except Exception as e:
            logger.error(f"Failed to get analyst estimates for {symbol}: {e}")
            return []

    def get_price_target(self, symbol: str) -> Optional[dict]:
        """Get price target consensus.

        Uses: /stable/price-target-consensus?symbol=
        """
        try:
            data = self._request("price-target-consensus", {"symbol": symbol})
            return data[0] if data else None
        except Exception as e:
            logger.error(f"Failed to get price target for {symbol}: {e}")
            return None

    def get_historical_price(
        self, symbol: str, from_date: Optional[date] = None, to_date: Optional[date] = None
    ) -> list[dict]:
        """Get historical EOD prices.

        Uses: /stable/historical-price-eod/full?symbol=
        """
        params = {"symbol": symbol}
        if from_date:
            params["from"] = from_date.isoformat()
        if to_date:
            params["to"] = to_date.isoformat()

        try:
            data = self._request("historical-price-eod/full", params)
            # Response has 'historical' key with price data
            if isinstance(data, dict):
                return data.get("historical", [])
            return data or []
        except Exception as e:
            logger.error(f"Failed to get historical prices for {symbol}: {e}")
            return []

    def get_sector_performance(self) -> list[dict]:
        """Get sector performance snapshot.

        Uses: /stable/sector-performance-snapshot
        """
        try:
            data = self._request("sector-performance-snapshot")
            return data or []
        except Exception as e:
            logger.error(f"Failed to get sector performance: {e}")
            return []

    def get_most_active(self) -> list[dict]:
        """Get most active stocks.

        Uses: /stable/most-actives
        """
        try:
            data = self._request("most-actives")
            return data[:20] if data else []
        except Exception as e:
            logger.error(f"Failed to get most active: {e}")
            return []
