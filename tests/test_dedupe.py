"""Tests for deduplication module."""

from datetime import datetime

import pytest

from app.ingest.fmp_client import NewsItem
from app.normalize.dedupe import (
    DeduplicatedEvent,
    deduplicate_news,
    filter_by_universe,
    normalize_title,
    title_similarity,
)


class TestNormalizeTitle:
    """Test title normalization."""

    def test_lowercase(self):
        """Should lowercase titles."""
        assert "hello world" in normalize_title("Hello World")

    def test_remove_punctuation(self):
        """Should remove punctuation."""
        result = normalize_title("Hello, World!")
        assert "," not in result
        assert "!" not in result

    def test_remove_noise_words(self):
        """Should remove common noise words."""
        result = normalize_title("The quick brown fox")
        assert "the" not in result.split()


class TestTitleSimilarity:
    """Test title similarity calculation."""

    def test_identical_titles(self):
        """Identical titles should have similarity 1.0."""
        assert title_similarity("Hello World", "Hello World") == 1.0

    def test_similar_titles(self):
        """Similar titles should have high similarity."""
        sim = title_similarity(
            "NVIDIA reports strong earnings",
            "NVIDIA reports strong quarterly earnings"
        )
        assert sim > 0.7

    def test_different_titles(self):
        """Different titles should have low similarity."""
        sim = title_similarity(
            "NVIDIA reports earnings",
            "Apple launches new iPhone"
        )
        assert sim < 0.3


class TestDeduplicateNews:
    """Test news deduplication."""

    def test_empty_list(self):
        """Empty list should return empty."""
        assert deduplicate_news([]) == []

    def test_dedupe_same_url(self):
        """Same URL should be deduplicated."""
        items = [
            NewsItem(
                title="Title 1",
                text="Text 1",
                url="https://example.com/1",
                site="Site A",
                published_date=datetime.now(),
                tickers=["AAPL"],
            ),
            NewsItem(
                title="Title 2",
                text="Text 2",
                url="https://example.com/1",  # Same URL
                site="Site B",
                published_date=datetime.now(),
                tickers=["AAPL"],
            ),
        ]
        result = deduplicate_news(items)
        assert len(result) == 1

    def test_merge_similar_titles(self):
        """Similar titles should be merged."""
        items = [
            NewsItem(
                title="NVIDIA beats earnings expectations",
                text="Text 1",
                url="https://example.com/1",
                site="Site A",
                published_date=datetime.now(),
                tickers=["NVDA"],
            ),
            NewsItem(
                title="NVIDIA beats quarterly earnings expectations",
                text="Text 2",
                url="https://example.com/2",
                site="Site B",
                published_date=datetime.now(),
                tickers=["NVDA"],
            ),
        ]
        result = deduplicate_news(items, similarity_threshold=0.7)
        assert len(result) == 1
        # Should have both source URLs
        assert len(result[0].source_urls) == 2


class TestFilterByUniverse:
    """Test universe filtering."""

    def test_filter_keeps_universe_tickers(self):
        """Should keep events with universe tickers."""
        events = [
            DeduplicatedEvent(
                headline="Test",
                text="Text",
                source_urls=["https://example.com"],
                sources=["Site"],
                tickers=["AAPL", "UNKNOWN"],
                published_date="2025-01-10T00:00:00",
            ),
        ]
        universe = {"AAPL", "MSFT"}
        result = filter_by_universe(events, universe)
        assert len(result) == 1
        assert result[0].tickers == ["AAPL"]  # UNKNOWN filtered out

    def test_filter_removes_non_universe(self):
        """Should remove events with no universe tickers."""
        events = [
            DeduplicatedEvent(
                headline="Test",
                text="Text",
                source_urls=["https://example.com"],
                sources=["Site"],
                tickers=["UNKNOWN1", "UNKNOWN2"],
                published_date="2025-01-10T00:00:00",
            ),
        ]
        universe = {"AAPL", "MSFT"}
        result = filter_by_universe(events, universe)
        assert len(result) == 0
