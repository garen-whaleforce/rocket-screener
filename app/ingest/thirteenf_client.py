"""13F Holdings client (v7).

Handles institutional holdings data from 13F filings.
Used for "Smart Money" analysis.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class InstitutionalHolding:
    """Single institutional holding."""

    manager_name: str
    manager_cik: str
    shares: int
    value: float  # USD
    pct_of_portfolio: float
    change_shares: int  # vs previous quarter
    change_pct: float
    report_date: date


@dataclass
class SmartMoneySignal:
    """Smart money signal for a stock."""

    ticker: str
    total_institutional_ownership: float  # percentage
    top_holders: list[InstitutionalHolding]
    net_buying: bool  # True if institutions net buying
    notable_changes: list[str]  # Human-readable notable changes
    signal: str  # "bullish", "neutral", "bearish"


class ThirteenFClient:
    """Client for 13F holdings data.

    Note: In production, would use a data provider like:
    - WhaleWisdom
    - Fintel
    - SEC EDGAR directly
    """

    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        self.api_url = api_url
        self.api_key = api_key

    def get_institutional_holdings(
        self, ticker: str, limit: int = 10
    ) -> list[InstitutionalHolding]:
        """Get top institutional holders for a ticker.

        Args:
            ticker: Stock ticker
            limit: Max holders to return

        Returns:
            List of institutional holdings
        """
        # Placeholder implementation
        # In production, would call actual 13F data API
        logger.info(f"Getting institutional holdings for {ticker}")

        # Return placeholder data for now
        # Would be replaced with actual API call
        return []

    def get_smart_money_signal(self, ticker: str) -> Optional[SmartMoneySignal]:
        """Analyze 13F data to generate smart money signal.

        Args:
            ticker: Stock ticker

        Returns:
            Smart money signal analysis
        """
        holdings = self.get_institutional_holdings(ticker)

        if not holdings:
            return None

        # Calculate metrics
        total_ownership = sum(h.pct_of_portfolio for h in holdings)
        net_change = sum(h.change_shares for h in holdings)

        # Determine signal
        if net_change > 0:
            net_buying = True
            if net_change > 1000000:
                signal = "bullish"
            else:
                signal = "neutral"
        else:
            net_buying = False
            if net_change < -1000000:
                signal = "bearish"
            else:
                signal = "neutral"

        # Notable changes
        notable = []
        for h in holdings[:3]:
            if abs(h.change_pct) > 10:
                action = "增持" if h.change_pct > 0 else "減持"
                notable.append(f"{h.manager_name} {action} {abs(h.change_pct):.1f}%")

        return SmartMoneySignal(
            ticker=ticker,
            total_institutional_ownership=total_ownership,
            top_holders=holdings[:5],
            net_buying=net_buying,
            notable_changes=notable,
            signal=signal,
        )


def get_smart_money_snapshot(
    tickers: list[str],
) -> dict[str, SmartMoneySignal]:
    """Get smart money signals for multiple tickers.

    Args:
        tickers: List of tickers

    Returns:
        Dict of ticker -> smart money signal
    """
    client = ThirteenFClient()
    signals = {}

    for ticker in tickers:
        try:
            signal = client.get_smart_money_signal(ticker)
            if signal:
                signals[ticker] = signal
        except Exception as e:
            logger.warning(f"Failed to get smart money for {ticker}: {e}")

    return signals
