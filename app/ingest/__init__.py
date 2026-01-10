"""Data ingestion module."""

from .fmp_client import FMPClient, MarketQuote, NewsItem

__all__ = ["FMPClient", "MarketQuote", "NewsItem"]
