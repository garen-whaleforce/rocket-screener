"""Tests for event scoring module."""

from datetime import datetime, timedelta

import pytest

from app.features.event_scoring import (
    calculate_impact_score,
    calculate_recency_score,
    classify_event_type,
    score_events,
    select_top_events,
)
from app.normalize.dedupe import DeduplicatedEvent


class TestClassifyEventType:
    """Test event type classification."""

    def test_earnings_classification(self):
        """Should classify earnings events."""
        assert classify_event_type("NVIDIA beats earnings", "") == "earnings"
        assert classify_event_type("Q3 revenue exceeds estimates", "") == "earnings"

    def test_macro_classification(self):
        """Should classify macro events."""
        assert classify_event_type("Fed raises interest rates", "") == "macro"
        assert classify_event_type("CPI inflation data released", "") == "macro"

    def test_mna_classification(self):
        """Should classify M&A events."""
        assert classify_event_type("Company announces acquisition", "") == "mna"
        assert classify_event_type("Merger deal completed", "") == "mna"

    def test_other_classification(self):
        """Unclassified events should be 'other'."""
        assert classify_event_type("Random news headline", "") == "other"


class TestRecencyScore:
    """Test recency score calculation."""

    def test_recent_high_score(self):
        """Very recent events should have high score."""
        recent = (datetime.utcnow() - timedelta(minutes=30)).isoformat()
        score, hours = calculate_recency_score(recent)
        assert score >= 90
        assert hours < 1

    def test_old_low_score(self):
        """Old events should have low score."""
        old = (datetime.utcnow() - timedelta(days=3)).isoformat()
        score, hours = calculate_recency_score(old)
        assert score < 30
        assert hours > 48


class TestImpactScore:
    """Test impact score calculation."""

    def test_high_impact_ticker(self):
        """High impact tickers should boost score."""
        event = DeduplicatedEvent(
            headline="Test",
            text="",
            source_urls=["https://example.com"],
            sources=["Site"],
            tickers=["NVDA"],  # High impact
            published_date="2025-01-10T00:00:00",
        )
        score, level = calculate_impact_score(event)
        # Single high-impact ticker gives 30 points (threshold for medium is 40)
        assert score >= 30

    def test_price_move_boost(self):
        """Large price moves should boost score."""
        event = DeduplicatedEvent(
            headline="Test",
            text="",
            source_urls=["https://example.com"],
            sources=["Site"],
            tickers=["UNKNOWN"],
            published_date="2025-01-10T00:00:00",
        )
        # Without price change
        score1, _ = calculate_impact_score(event, price_changes={})
        # With large price change
        score2, _ = calculate_impact_score(event, price_changes={"UNKNOWN": 10.0})
        assert score2 > score1


class TestSelectTopEvents:
    """Test top event selection."""

    def test_respects_max_count(self):
        """Should not exceed max count."""
        # Create 10 scored events
        from app.features.event_scoring import ScoredEvent

        events = []
        for i in range(10):
            event = DeduplicatedEvent(
                headline=f"Event {i}",
                text="",
                source_urls=["https://example.com"],
                sources=["Site"],
                tickers=[f"TICK{i}"],
                published_date="2025-01-10T00:00:00",
            )
            events.append(ScoredEvent(
                event=event,
                score=100 - i,
                event_type="other",
                impact_level="medium",
                recency_hours=1,
            ))

        selected = select_top_events(events, min_count=5, max_count=8)
        assert len(selected) <= 8

    def test_respects_min_count(self):
        """Should try to meet min count."""
        from app.features.event_scoring import ScoredEvent

        events = []
        for i in range(3):
            event = DeduplicatedEvent(
                headline=f"Event {i}",
                text="",
                source_urls=["https://example.com"],
                sources=["Site"],
                tickers=[f"TICK{i}"],
                published_date="2025-01-10T00:00:00",
            )
            events.append(ScoredEvent(
                event=event,
                score=100 - i,
                event_type="other",
                impact_level="medium",
                recency_hours=1,
            ))

        selected = select_top_events(events, min_count=5, max_count=8)
        # Should have all 3 (less than min, but that's all we have)
        assert len(selected) == 3
