"""FMP (Financial Modeling Prep) API client.

Handles all data ingestion from FMP Premium API:
- Market quotes (indices, ETFs, macro assets)
- Stock news
- Company profiles
- Financial statements
- Valuation metrics
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

import requests

from app.config import FMPConfig

logger = logging.getLogger(__name__)


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
    """Client for FMP Premium API."""

    def __init__(self, config: FMPConfig):
        self.config = config
        self.base_url = config.base_url.rstrip("/")

    def _request(
        self, endpoint: str, params: Optional[dict] = None
    ) -> Any:
        """Make API request."""
        url = f"{self.base_url}/{endpoint}"
        all_params = {"apikey": self.config.api_key}
        if params:
            all_params.update(params)

        logger.debug(f"FMP request: {endpoint}")
        response = requests.get(url, params=all_params, timeout=30)
        response.raise_for_status()

        return response.json()

    def get_market_snapshot(self) -> dict[str, MarketQuote]:
        """Get market snapshot for key indices and assets.

        Returns quotes for:
        - SPY, QQQ, DIA (index ETFs)
        - ^TNX (10Y yield)
        - DX-Y.NYB (DXY)
        - CL=F (Oil)
        - GC=F (Gold)
        - BTCUSD
        """
        symbols = {
            "SPY": "S&P 500 ETF",
            "QQQ": "Nasdaq 100 ETF",
            "DIA": "道瓊工業 ETF",
        }

        # Get ETF quotes
        quotes = {}
        try:
            data = self._request("quote/SPY,QQQ,DIA")
            for item in data:
                symbol = item["symbol"]
                quotes[symbol] = MarketQuote(
                    symbol=symbol,
                    name=symbols.get(symbol, symbol),
                    price=item.get("price", 0),
                    change=item.get("change", 0),
                    change_percent=item.get("changesPercentage", 0),
                )
        except Exception as e:
            logger.warning(f"Failed to get ETF quotes: {e}")

        # Get crypto (Bitcoin)
        try:
            data = self._request("quote/BTCUSD")
            if data:
                item = data[0]
                quotes["BTC"] = MarketQuote(
                    symbol="BTC",
                    name="Bitcoin",
                    price=item.get("price", 0),
                    change=item.get("change", 0),
                    change_percent=item.get("changesPercentage", 0),
                )
        except Exception as e:
            logger.warning(f"Failed to get BTC quote: {e}")

        # Get commodities
        try:
            data = self._request("quote/GCUSD,CLUSD")
            for item in data:
                symbol = item["symbol"]
                name = "黃金" if "GC" in symbol else "原油 (WTI)"
                display_symbol = "Gold" if "GC" in symbol else "Oil"
                quotes[display_symbol] = MarketQuote(
                    symbol=display_symbol,
                    name=name,
                    price=item.get("price", 0),
                    change=item.get("change", 0),
                    change_percent=item.get("changesPercentage", 0),
                )
        except Exception as e:
            logger.warning(f"Failed to get commodity quotes: {e}")

        # Get treasury yield
        try:
            data = self._request("treasury", {"from": date.today().isoformat()})
            if data:
                latest = data[0]
                quotes["10Y"] = MarketQuote(
                    symbol="10Y",
                    name="10Y 殖利率",
                    price=latest.get("year10", 0),
                    change=0,  # FMP treasury doesn't provide change
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

        Args:
            tickers: Optional list of tickers to filter by
            limit: Maximum number of news items

        Returns:
            List of news items
        """
        params = {"limit": limit}
        if tickers:
            params["tickers"] = ",".join(tickers)

        try:
            data = self._request("stock_news", params)
        except Exception as e:
            logger.error(f"Failed to get stock news: {e}")
            return []

        news_items = []
        for item in data:
            try:
                # Parse published date
                pub_date_str = item.get("publishedDate", "")
                try:
                    pub_date = datetime.fromisoformat(
                        pub_date_str.replace("Z", "+00:00")
                    )
                except ValueError:
                    pub_date = datetime.now()

                # Extract tickers
                ticker_str = item.get("symbol", "")
                item_tickers = [t.strip() for t in ticker_str.split(",") if t.strip()]

                news_items.append(
                    NewsItem(
                        title=item.get("title", ""),
                        text=item.get("text", ""),
                        url=item.get("url", ""),
                        site=item.get("site", ""),
                        published_date=pub_date,
                        tickers=item_tickers,
                        image_url=item.get("image"),
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to parse news item: {e}")
                continue

        return news_items

    def get_general_news(self, limit: int = 30) -> list[NewsItem]:
        """Get general market news."""
        try:
            data = self._request("fmp/articles", {"page": 0, "size": limit})
        except Exception as e:
            logger.error(f"Failed to get general news: {e}")
            return []

        news_items = []
        content = data.get("content", []) if isinstance(data, dict) else data
        for item in content:
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

    def get_quote(self, symbol: str) -> Optional[dict]:
        """Get quote for a single symbol."""
        try:
            data = self._request(f"quote/{symbol}")
            return data[0] if data else None
        except Exception as e:
            logger.error(f"Failed to get quote for {symbol}: {e}")
            return None

    def get_company_profile(self, symbol: str) -> Optional[dict]:
        """Get company profile."""
        try:
            data = self._request(f"profile/{symbol}")
            return data[0] if data else None
        except Exception as e:
            logger.error(f"Failed to get profile for {symbol}: {e}")
            return None

    def get_financial_ratios(self, symbol: str) -> Optional[dict]:
        """Get financial ratios (TTM)."""
        try:
            data = self._request(f"ratios-ttm/{symbol}")
            return data[0] if data else None
        except Exception as e:
            logger.error(f"Failed to get ratios for {symbol}: {e}")
            return None

    def get_key_metrics(self, symbol: str) -> Optional[dict]:
        """Get key metrics (TTM)."""
        try:
            data = self._request(f"key-metrics-ttm/{symbol}")
            return data[0] if data else None
        except Exception as e:
            logger.error(f"Failed to get metrics for {symbol}: {e}")
            return None

    def get_income_statement(
        self, symbol: str, period: str = "quarter", limit: int = 4
    ) -> list[dict]:
        """Get income statements."""
        try:
            data = self._request(
                f"income-statement/{symbol}",
                {"period": period, "limit": limit},
            )
            return data or []
        except Exception as e:
            logger.error(f"Failed to get income statement for {symbol}: {e}")
            return []

    def get_stock_peers(self, symbol: str) -> list[str]:
        """Get stock peers/competitors."""
        try:
            data = self._request(f"stock_peers", {"symbol": symbol})
            if data and len(data) > 0:
                return data[0].get("peersList", [])
            return []
        except Exception as e:
            logger.error(f"Failed to get peers for {symbol}: {e}")
            return []

    def get_gainers_losers(self) -> dict[str, list[dict]]:
        """Get market gainers and losers."""
        result = {"gainers": [], "losers": []}

        try:
            gainers = self._request("stock_market/gainers")
            result["gainers"] = gainers[:10] if gainers else []
        except Exception as e:
            logger.warning(f"Failed to get gainers: {e}")

        try:
            losers = self._request("stock_market/losers")
            result["losers"] = losers[:10] if losers else []
        except Exception as e:
            logger.warning(f"Failed to get losers: {e}")

        return result

    def get_sp500_constituents(self) -> list[str]:
        """Get S&P 500 constituent symbols."""
        try:
            data = self._request("sp500_constituent")
            return [item["symbol"] for item in data] if data else []
        except Exception as e:
            logger.error(f"Failed to get S&P 500 constituents: {e}")
            return []
