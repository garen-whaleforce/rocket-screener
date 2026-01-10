"""Earnings call transcript client (v5).

Connects to internal transcript API (earningscall.biz).
Extracts structured information from transcripts.
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

    def __post_init__(self):
        if self.key_topics is None:
            self.key_topics = []
        if self.new_products is None:
            self.new_products = []
        if self.risks_mentioned is None:
            self.risks_mentioned = []
        if self.qa_highlights is None:
            self.qa_highlights = []


class TranscriptClient:
    """Client for internal transcript API."""

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
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        response = requests.get(url, params=params, headers=headers, timeout=60)
        response.raise_for_status()
        return response.json()

    def get_latest_transcript(self, ticker: str) -> Optional[dict]:
        """Get the most recent transcript for a ticker.

        Returns raw transcript data.
        """
        try:
            data = self._request(f"transcripts/{ticker}/latest")
            return data
        except Exception as e:
            logger.error(f"Failed to get transcript for {ticker}: {e}")
            return None

    def get_transcript_by_quarter(
        self, ticker: str, year: int, quarter: int
    ) -> Optional[dict]:
        """Get transcript for specific quarter.

        Args:
            ticker: Stock ticker
            year: Fiscal year
            quarter: Quarter (1-4)

        Returns:
            Raw transcript data
        """
        try:
            data = self._request(
                f"transcripts/{ticker}",
                params={"year": year, "quarter": quarter},
            )
            return data
        except Exception as e:
            logger.error(f"Failed to get transcript for {ticker} Q{quarter} {year}: {e}")
            return None

    def extract_structured_data(
        self, raw_transcript: dict
    ) -> Optional[TranscriptExtract]:
        """Extract structured data from raw transcript.

        This is a simplified extraction. In production, would use
        LLM for more sophisticated extraction.

        Args:
            raw_transcript: Raw transcript data

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

        # Extract text content
        text = raw_transcript.get("content", "").lower()

        # Simple keyword-based extraction
        guidance = {}
        if "guidance" in text or "outlook" in text:
            guidance["mentioned"] = True

        # Detect tone
        positive_words = ["strong", "growth", "exceed", "beat", "optimistic"]
        negative_words = ["challenging", "decline", "headwind", "cautious"]

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
        topic_keywords = ["ai", "margin", "revenue", "growth", "demand", "supply chain"]
        for kw in topic_keywords:
            if kw in text:
                key_topics.append(kw.upper())

        # Detect new products
        new_products = []
        if "new product" in text or "launch" in text:
            new_products.append("新產品提及")

        # Detect risks
        risks = []
        risk_keywords = ["risk", "competition", "regulatory", "tariff", "macro"]
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
