"""SEC EDGAR client (v6).

Handles SEC filings for:
- Event detection (8-K, 4, etc.)
- Financial verification (10-K, 10-Q)
- Data cross-validation
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

SEC_BASE_URL = "https://data.sec.gov"
SEC_SUBMISSIONS_URL = f"{SEC_BASE_URL}/submissions"
SEC_FILINGS_URL = "https://www.sec.gov/cgi-bin/browse-edgar"


@dataclass
class SECFiling:
    """SEC filing metadata."""

    accession_number: str
    form_type: str
    filing_date: date
    description: str
    primary_document: str
    filing_url: str


@dataclass
class SECEvent:
    """Detected SEC event from filings."""

    ticker: str
    cik: str
    form_type: str
    filing_date: date
    event_type: str  # insider_trade, 8k_event, earnings, etc.
    description: str
    url: str
    importance: str  # high, medium, low


class SECClient:
    """Client for SEC EDGAR data."""

    def __init__(self):
        self.headers = {
            "User-Agent": "RocketScreener research@example.com",
            "Accept": "application/json",
        }

    def _get_cik(self, ticker: str) -> Optional[str]:
        """Get CIK for a ticker.

        Note: In production, would use a maintained ticker->CIK mapping.
        """
        # Simplified: would use SEC company tickers JSON
        # https://www.sec.gov/files/company_tickers.json
        try:
            response = requests.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            for entry in data.values():
                if entry.get("ticker", "").upper() == ticker.upper():
                    cik = str(entry.get("cik_str", ""))
                    return cik.zfill(10)  # CIK needs to be 10 digits

            return None
        except Exception as e:
            logger.error(f"Failed to get CIK for {ticker}: {e}")
            return None

    def get_recent_filings(
        self, ticker: str, limit: int = 10
    ) -> list[SECFiling]:
        """Get recent filings for a ticker.

        Args:
            ticker: Stock ticker
            limit: Maximum filings to return

        Returns:
            List of recent filings
        """
        cik = self._get_cik(ticker)
        if not cik:
            logger.warning(f"Could not find CIK for {ticker}")
            return []

        try:
            url = f"{SEC_SUBMISSIONS_URL}/CIK{cik}.json"
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            filings = []
            recent = data.get("filings", {}).get("recent", {})

            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accessions = recent.get("accessionNumber", [])
            docs = recent.get("primaryDocument", [])
            descs = recent.get("primaryDocDescription", [])

            for i in range(min(limit, len(forms))):
                accession = accessions[i].replace("-", "")
                filing_url = (
                    f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/"
                    f"{docs[i]}"
                )

                filings.append(
                    SECFiling(
                        accession_number=accessions[i],
                        form_type=forms[i],
                        filing_date=date.fromisoformat(dates[i]),
                        description=descs[i] if i < len(descs) else "",
                        primary_document=docs[i],
                        filing_url=filing_url,
                    )
                )

            return filings

        except Exception as e:
            logger.error(f"Failed to get filings for {ticker}: {e}")
            return []

    def detect_events(
        self, ticker: str, days_back: int = 7
    ) -> list[SECEvent]:
        """Detect notable SEC events for a ticker.

        Args:
            ticker: Stock ticker
            days_back: How many days to look back

        Returns:
            List of detected events
        """
        filings = self.get_recent_filings(ticker, limit=20)
        events = []
        cutoff = date.today()

        cik = self._get_cik(ticker)
        if not cik:
            return []

        for filing in filings:
            # Skip old filings
            days_old = (cutoff - filing.filing_date).days
            if days_old > days_back:
                continue

            # Classify event
            form = filing.form_type.upper()

            if form in ("4", "3", "5"):
                # Insider trading
                events.append(
                    SECEvent(
                        ticker=ticker,
                        cik=cik,
                        form_type=form,
                        filing_date=filing.filing_date,
                        event_type="insider_trade",
                        description=f"Insider transaction (Form {form})",
                        url=filing.filing_url,
                        importance="medium",
                    )
                )
            elif form == "8-K":
                events.append(
                    SECEvent(
                        ticker=ticker,
                        cik=cik,
                        form_type=form,
                        filing_date=filing.filing_date,
                        event_type="8k_event",
                        description="Material event disclosure",
                        url=filing.filing_url,
                        importance="high",
                    )
                )
            elif form in ("10-K", "10-Q"):
                events.append(
                    SECEvent(
                        ticker=ticker,
                        cik=cik,
                        form_type=form,
                        filing_date=filing.filing_date,
                        event_type="earnings",
                        description=f"Financial report ({form})",
                        url=filing.filing_url,
                        importance="high",
                    )
                )

        return events


def get_sec_events_for_universe(
    universe: set[str], days_back: int = 3
) -> dict[str, list[SECEvent]]:
    """Get SEC events for all tickers in universe.

    Args:
        universe: Set of tickers
        days_back: Days to look back

    Returns:
        Dict of ticker -> events
    """
    client = SECClient()
    all_events = {}

    for ticker in universe:
        try:
            events = client.detect_events(ticker, days_back)
            if events:
                all_events[ticker] = events
        except Exception as e:
            logger.warning(f"Failed to get SEC events for {ticker}: {e}")

    return all_events
