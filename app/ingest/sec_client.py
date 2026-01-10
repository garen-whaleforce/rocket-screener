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
    summary: Optional[str] = None  # LLM-generated summary


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


def fetch_filing_text(filing_url: str, max_chars: int = 10000) -> Optional[str]:
    """Fetch filing text content for summarization.

    Args:
        filing_url: URL to the SEC filing document
        max_chars: Maximum characters to fetch

    Returns:
        Text content of the filing, or None if failed
    """
    try:
        headers = {"User-Agent": "RocketScreener research@example.com"}
        response = requests.get(filing_url, headers=headers, timeout=30)
        response.raise_for_status()

        content = response.text
        # Clean HTML if present
        if "<html" in content.lower():
            import re
            # Remove HTML tags
            content = re.sub(r'<[^>]+>', ' ', content)
            # Remove extra whitespace
            content = re.sub(r'\s+', ' ', content)

        return content[:max_chars]
    except Exception as e:
        logger.warning(f"Failed to fetch filing content: {e}")
        return None


def summarize_filing_with_llm(
    filing: SECFiling,
    ticker: str,
    llm_client=None,
) -> Optional[str]:
    """Generate LLM summary of SEC filing.

    Args:
        filing: SEC filing metadata
        ticker: Stock ticker
        llm_client: LLM client (optional, will get default if None)

    Returns:
        Summary string, or None if failed
    """
    if llm_client is None:
        try:
            from app.llm.client import get_llm_client
            llm_client = get_llm_client()
        except Exception:
            return None

    if not llm_client:
        return None

    # Fetch filing content
    content = fetch_filing_text(filing.filing_url, max_chars=8000)
    if not content:
        return None

    form_type = filing.form_type.upper()

    prompt = f"""請簡要摘要以下 {ticker} 的 SEC {form_type} 文件重點（50字以內，中文回答）：

{content[:6000]}

摘要："""

    try:
        summary = llm_client.generate(prompt=prompt, max_tokens=100, temperature=0.3)
        return summary.strip()[:200]  # Safety limit
    except Exception as e:
        logger.warning(f"Failed to summarize filing: {e}")
        return None


def enhance_events_with_summaries(
    events: list[SECEvent],
    max_events: int = 3,
) -> list[SECEvent]:
    """Add LLM summaries to high-importance SEC events.

    Args:
        events: List of SEC events
        max_events: Maximum events to summarize (for rate limiting)

    Returns:
        Events with summaries added
    """
    try:
        from app.llm.client import get_llm_client
        llm_client = get_llm_client()
    except Exception:
        return events

    if not llm_client:
        return events

    # Only summarize high importance events
    high_importance = [e for e in events if e.importance == "high"][:max_events]

    for event in high_importance:
        if event.form_type in ("8-K", "10-K", "10-Q"):
            content = fetch_filing_text(event.url, max_chars=6000)
            if content:
                prompt = f"""請簡要摘要 {event.ticker} 的 {event.form_type} 文件重點（30字以內，中文）：

{content[:4000]}

摘要："""
                try:
                    summary = llm_client.generate(prompt=prompt, max_tokens=80, temperature=0.3)
                    event.summary = summary.strip()[:100]
                    logger.info(f"Added summary to {event.ticker} {event.form_type}")
                except Exception as e:
                    logger.warning(f"Failed to summarize {event.ticker} {event.form_type}: {e}")

    return events
