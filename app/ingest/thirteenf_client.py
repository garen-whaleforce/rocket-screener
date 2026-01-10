"""13F Holdings client (v7).

Handles institutional holdings data from 13F filings.
Data source: MinIO storage (13f bucket).
Used for "Smart Money" analysis.
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import date
from typing import Optional

import boto3
from botocore.client import Config

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
    """Client for 13F holdings data from MinIO.

    Data structure in MinIO:
    13f/{year}/{cik}/filing.json
    """

    def __init__(self):
        # MinIO configuration from environment
        self.endpoint = os.environ.get(
            "MINIO_ENDPOINT", "https://minio.api.whaleforce.dev"
        )
        self.access_key = os.environ.get("MINIO_ACCESS_KEY", "whaleforce")
        self.secret_key = os.environ.get("MINIO_SECRET_KEY", "whaleforce.ai")
        self.bucket = "13f"

        # Initialize S3 client
        self.s3 = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(signature_version="s3v4"),
        )

        # Ticker to CIK mapping cache
        self._ticker_cik_map: dict[str, str] = {}

    def _get_cik_for_ticker(self, ticker: str) -> Optional[str]:
        """Get CIK for a ticker.

        Uses SEC company_tickers.json for mapping.
        """
        if ticker in self._ticker_cik_map:
            return self._ticker_cik_map[ticker]

        try:
            import requests

            response = requests.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers={"User-Agent": "RocketScreener research@example.com"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            for entry in data.values():
                t = entry.get("ticker", "").upper()
                cik = str(entry.get("cik_str", "")).zfill(10)
                self._ticker_cik_map[t] = cik
                if t == ticker.upper():
                    return cik

            return None
        except Exception as e:
            logger.warning(f"Failed to get CIK for {ticker}: {e}")
            return None

    def _list_filings_for_cik(self, cik: str, year: int = None) -> list[str]:
        """List available filings for a CIK.

        Args:
            cik: Company CIK
            year: Specific year or None for latest

        Returns:
            List of object keys
        """
        if year is None:
            year = date.today().year

        prefix = f"{year}/{cik}/"
        try:
            response = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
            keys = [obj["Key"] for obj in response.get("Contents", [])]
            return keys
        except Exception as e:
            logger.warning(f"Failed to list filings for CIK {cik}: {e}")
            return []

    def _get_filing_data(self, key: str) -> Optional[dict]:
        """Get filing data from MinIO.

        Args:
            key: Object key

        Returns:
            Filing data as dict
        """
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=key)
            content = response["Body"].read()
            return json.loads(content)
        except Exception as e:
            logger.warning(f"Failed to get filing {key}: {e}")
            return None

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
        logger.info(f"Getting institutional holdings for {ticker} from MinIO")

        cik = self._get_cik_for_ticker(ticker)
        if not cik:
            logger.warning(f"Could not find CIK for {ticker}")
            return []

        # Try current year, then previous year
        current_year = date.today().year
        filings = self._list_filings_for_cik(cik, current_year)
        if not filings:
            filings = self._list_filings_for_cik(cik, current_year - 1)

        if not filings:
            logger.info(f"No 13F filings found for {ticker}")
            return []

        # Get latest filing
        latest_key = sorted(filings)[-1]
        data = self._get_filing_data(latest_key)
        if not data:
            return []

        # Parse holdings from filing data
        holdings = []
        filing_info = data.get("filingInfo", {})
        report_date_str = filing_info.get("filingDate", str(date.today()))
        try:
            report_date = date.fromisoformat(report_date_str[:10])
        except ValueError:
            report_date = date.today()

        # Parse holdings - structure may vary by data source
        raw_holdings = data.get("holdings", data.get("infotable", []))

        for h in raw_holdings[:limit]:
            try:
                shares = int(h.get("shrsOrPrnAmt", {}).get("sshPrnamt", 0))
                value = float(h.get("value", 0)) * 1000  # Often in thousands

                # Calculate change if available
                prev_shares = int(h.get("previousShares", shares))
                change_shares = shares - prev_shares
                change_pct = (change_shares / prev_shares * 100) if prev_shares else 0

                holdings.append(
                    InstitutionalHolding(
                        manager_name=data.get("filerInfo", {}).get("name", "Unknown"),
                        manager_cik=data.get("filerInfo", {}).get("cik", ""),
                        shares=shares,
                        value=value,
                        pct_of_portfolio=float(h.get("pctOfPortfolio", 0)),
                        change_shares=change_shares,
                        change_pct=change_pct,
                        report_date=report_date,
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to parse holding: {e}")
                continue

        return holdings

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
        for h in holdings[:5]:
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
