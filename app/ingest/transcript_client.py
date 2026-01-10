"""Earnings call transcript client (v5).

Connects to internal transcript API (earningcall.gpu5090.whaleforce.dev).
Extracts structured information from transcripts.

API Endpoints:
- /api/companies/search?q={query} - Search companies
- /api/company/{symbol}/events - Get earnings events
- /api/company/{symbol}/transcript?year={year}&quarter={quarter}&level={1-4}
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import requests

from app.config import TranscriptConfig

logger = logging.getLogger(__name__)


@dataclass
class TranscriptExtract:
    """Extracted information from earnings call transcript."""

    ticker: str
    quarter: str  # e.g., "Q3 2024"
    call_date: datetime

    # Guidance and outlook
    guidance: Optional[dict] = None  # revenue_guidance, eps_guidance, etc.
    outlook_tone: str = "neutral"  # bullish, neutral, cautious

    # Key topics
    key_topics: list[str] = None
    new_products: list[str] = None
    risks_mentioned: list[str] = None

    # Q&A highlights
    qa_highlights: list[dict] = None  # [{question, answer_summary}]

    # Management sentiment
    sentiment_score: float = 0.5  # 0-1, higher = more positive

    # Speaker breakdown (from level 2+)
    speakers: list[dict] = None  # [{name, title, text}]

    def __post_init__(self):
        if self.key_topics is None:
            self.key_topics = []
        if self.new_products is None:
            self.new_products = []
        if self.risks_mentioned is None:
            self.risks_mentioned = []
        if self.qa_highlights is None:
            self.qa_highlights = []
        if self.speakers is None:
            self.speakers = []


class TranscriptClient:
    """Client for internal transcript API (earningcall.gpu5090.whaleforce.dev)."""

    def __init__(self, config: TranscriptConfig):
        self.config = config
        self.base_url = config.api_url.rstrip("/") if config.api_url else ""

    def _request(self, endpoint: str, params: Optional[dict] = None) -> Any:
        """Make API request."""
        if not self.base_url:
            raise ValueError("Transcript API URL not configured")

        url = f"{self.base_url}/{endpoint}"
        headers = {}
        if self.config.api_key:
            headers["X-API-Key"] = self.config.api_key

        response = requests.get(url, params=params, headers=headers, timeout=60)
        response.raise_for_status()
        return response.json()

    def search_companies(self, query: str) -> list[dict]:
        """Search for companies by symbol or name.

        Args:
            query: Search query (e.g., "AAPL" or "Apple")

        Returns:
            List of matching companies
        """
        try:
            data = self._request("api/companies/search", params={"q": query})
            return data.get("companies", [])
        except Exception as e:
            logger.error(f"Failed to search companies for '{query}': {e}")
            return []

    def get_company_events(self, ticker: str) -> list[dict]:
        """Get all earnings events for a company.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of earnings events with year and quarter
        """
        try:
            data = self._request(f"api/company/{ticker}/events")
            return data.get("events", [])
        except Exception as e:
            logger.error(f"Failed to get events for {ticker}: {e}")
            return []

    def get_latest_transcript(self, ticker: str, level: int = 2) -> Optional[dict]:
        """Get the most recent transcript for a ticker.

        Args:
            ticker: Stock ticker symbol
            level: Detail level (1=text, 2=speakers, 3=timestamps, 4=structured)

        Returns:
            Raw transcript data
        """
        try:
            # First get events to find latest quarter
            events = self.get_company_events(ticker)
            if not events:
                logger.warning(f"No earnings events found for {ticker}")
                return None

            # Events are typically sorted, get the most recent
            latest = events[0]
            year = latest.get("year")
            quarter = latest.get("quarter")

            if not year or not quarter:
                logger.warning(f"Invalid event data for {ticker}: {latest}")
                return None

            return self.get_transcript_by_quarter(ticker, year, quarter, level)
        except Exception as e:
            logger.error(f"Failed to get latest transcript for {ticker}: {e}")
            return None

    def get_transcript_by_quarter(
        self, ticker: str, year: int, quarter: int, level: int = 2
    ) -> Optional[dict]:
        """Get transcript for specific quarter.

        Args:
            ticker: Stock ticker
            year: Fiscal year
            quarter: Quarter (1-4)
            level: Detail level (1=text, 2=speakers, 3=timestamps, 4=structured)

        Returns:
            Raw transcript data with 'text' or 'speakers' field
        """
        try:
            data = self._request(
                f"api/company/{ticker}/transcript",
                params={"year": year, "quarter": quarter, "level": level},
            )
            # Add metadata for downstream processing
            data["ticker"] = ticker
            data["year"] = year
            data["quarter"] = f"Q{quarter} {year}"
            return data
        except Exception as e:
            logger.error(f"Failed to get transcript for {ticker} Q{quarter} {year}: {e}")
            return None

    def get_sp500_companies(self) -> list[dict]:
        """Get list of S&P 500 companies.

        Returns:
            List of S&P 500 company info
        """
        try:
            data = self._request("api/companies/sp500")
            return data.get("companies", [])
        except Exception as e:
            logger.error(f"Failed to get S&P 500 companies: {e}")
            return []

    def get_earnings_calendar(self, date_str: str) -> list[dict]:
        """Get earnings calendar for a specific date.

        Args:
            date_str: Date in YYYY-MM-DD format

        Returns:
            List of earnings events for the date
        """
        try:
            data = self._request("api/calendar", params={"date_str": date_str})
            return data.get("events", [])
        except Exception as e:
            logger.error(f"Failed to get earnings calendar for {date_str}: {e}")
            return []

    def extract_structured_data(
        self, raw_transcript: dict
    ) -> Optional[TranscriptExtract]:
        """Extract structured data from raw transcript.

        Handles both level 1 (text only) and level 2+ (speakers) response formats.

        Args:
            raw_transcript: Raw transcript data from API

        Returns:
            Structured transcript extract
        """
        if not raw_transcript:
            return None

        ticker = raw_transcript.get("ticker", "")
        quarter = raw_transcript.get("quarter", "")
        call_date_str = raw_transcript.get("date", "")

        try:
            call_date = datetime.fromisoformat(call_date_str.replace("Z", "+00:00"))
        except ValueError:
            call_date = datetime.now()

        # Extract text content - handle both 'text' and 'speakers' formats
        speakers = raw_transcript.get("speakers", [])
        if speakers:
            # Level 2+ format: combine speaker texts
            text = " ".join(s.get("text", "") for s in speakers).lower()
        else:
            # Level 1 format: direct text field
            text = raw_transcript.get("text", raw_transcript.get("content", "")).lower()

        # Simple keyword-based extraction
        guidance = {}
        if "guidance" in text or "outlook" in text:
            guidance["mentioned"] = True

        # Detect tone
        positive_words = ["strong", "growth", "exceed", "beat", "optimistic", "confident"]
        negative_words = ["challenging", "decline", "headwind", "cautious", "uncertain"]

        positive_count = sum(1 for w in positive_words if w in text)
        negative_count = sum(1 for w in negative_words if w in text)

        if positive_count > negative_count + 2:
            outlook_tone = "bullish"
            sentiment_score = 0.7
        elif negative_count > positive_count + 2:
            outlook_tone = "cautious"
            sentiment_score = 0.3
        else:
            outlook_tone = "neutral"
            sentiment_score = 0.5

        # Extract key topics (simplified)
        key_topics = []
        topic_keywords = ["ai", "margin", "revenue", "growth", "demand", "supply chain", "cloud"]
        for kw in topic_keywords:
            if kw in text:
                key_topics.append(kw.upper())

        # Detect new products
        new_products = []
        if "new product" in text or "launch" in text or "announced" in text:
            new_products.append("新產品提及")

        # Detect risks
        risks = []
        risk_keywords = ["risk", "competition", "regulatory", "tariff", "macro", "inflation"]
        for kw in risk_keywords:
            if kw in text:
                risks.append(kw.capitalize())

        return TranscriptExtract(
            ticker=ticker,
            quarter=quarter,
            call_date=call_date,
            guidance=guidance,
            outlook_tone=outlook_tone,
            key_topics=key_topics[:5],
            new_products=new_products,
            risks_mentioned=risks[:3],
            sentiment_score=sentiment_score,
            speakers=speakers,
        )


def get_management_signals(
    transcript_extract: Optional[TranscriptExtract],
) -> dict:
    """Convert transcript extract to management signals for Article 2.

    Args:
        transcript_extract: Extracted transcript data

    Returns:
        Dict of management signals for evidence pack
    """
    if not transcript_extract:
        return {}

    return {
        "quarter": transcript_extract.quarter,
        "call_date": transcript_extract.call_date.isoformat(),
        "outlook_tone": transcript_extract.outlook_tone,
        "sentiment_score": transcript_extract.sentiment_score,
        "key_topics": transcript_extract.key_topics,
        "risks_mentioned": transcript_extract.risks_mentioned,
        "guidance_mentioned": transcript_extract.guidance.get("mentioned", False)
        if transcript_extract.guidance
        else False,
    }


def extract_with_llm(
    client: TranscriptClient,
    ticker: str,
    llm_client=None,
) -> tuple[Optional[TranscriptExtract], Optional[dict]]:
    """Extract transcript data using LLM for enhanced analysis.

    Two-stage extraction:
    1. Fetch raw transcript from API
    2. Use LLM to extract structured information with chunking

    Args:
        client: TranscriptClient instance
        ticker: Stock ticker symbol
        llm_client: Optional LLM client (uses default if None)

    Returns:
        Tuple of (TranscriptExtract, raw_merged_data)
    """
    # Get LLM client if not provided
    if llm_client is None:
        try:
            from app.llm.client import get_llm_client
            llm_client = get_llm_client()
        except Exception as e:
            logger.warning(f"Failed to get LLM client: {e}")
            return None, None

    if not llm_client:
        logger.warning("LLM client not available for transcript extraction")
        return None, None

    # Fetch raw transcript
    raw_transcript = client.get_latest_transcript(ticker, level=2)
    if not raw_transcript:
        logger.warning(f"No transcript found for {ticker}")
        return None, None

    # Use LLM extraction
    try:
        from app.llm.extract_transcript_json import extract_transcript_with_llm

        extract = extract_transcript_with_llm(raw_transcript, llm_client)
        return extract, None  # merged_data captured internally

    except Exception as e:
        logger.error(f"LLM transcript extraction failed for {ticker}: {e}")
        # Fallback to keyword-based extraction
        extract = client.extract_structured_data(raw_transcript)
        return extract, None
