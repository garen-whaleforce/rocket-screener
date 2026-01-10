"""Evidence Pack schemas using Pydantic.

Evidence Packs are the single source of truth for article generation.
LLM must only use data from Evidence Packs, never invent numbers.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class MarketSnapshotItem(BaseModel):
    """Single item in market snapshot."""

    symbol: str
    name: str
    close: float
    change: float
    change_pct: float

    def format_change(self) -> str:
        """Format change for display."""
        sign = "+" if self.change >= 0 else ""
        return f"{sign}{self.change:.2f}"

    def format_change_pct(self) -> str:
        """Format change percent for display."""
        sign = "+" if self.change_pct >= 0 else ""
        return f"{sign}{self.change_pct:.2f}%"


class TopEvent(BaseModel):
    """Top event for article 1."""

    rank: int
    tickers: list[str]
    event_type: str
    headline: str
    what_happened: str
    why_important: Optional[str] = None
    impact: Optional[str] = None
    next_watch: Optional[str] = None
    source_urls: list[str]
    key_numbers: Optional[dict] = None


class Article1Evidence(BaseModel):
    """Evidence Pack for Article 1 (Daily Brief)."""

    date: date
    market_snapshot: list[MarketSnapshotItem]
    top_events: list[TopEvent]
    watch_tonight: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


class ValuationCase(BaseModel):
    """Valuation case (Bull/Base/Bear)."""

    scenario: str  # "bull", "base", "bear"
    assumption: str
    target_price: float
    upside_pct: float
    key_drivers: list[str] = Field(default_factory=list)


class FinancialMetric(BaseModel):
    """Financial metric with period comparison."""

    name: str
    current: str
    previous: Optional[str] = None
    yoy_change: Optional[str] = None


class CompetitorInfo(BaseModel):
    """Competitor information."""

    ticker: str
    name: str
    market_cap: str
    pe_ratio: Optional[float] = None
    revenue_growth: Optional[str] = None


class Article2Evidence(BaseModel):
    """Evidence Pack for Article 2 (Stock Deep Dive)."""

    date: date
    ticker: str
    company_name: str

    # Company info
    sector: str
    industry: str
    exchange: str
    market_cap: str
    description: str

    # Price info
    current_price: float
    price_change_1d: float
    price_change_5d: Optional[float] = None

    # Financial metrics
    key_metrics: list[FinancialMetric] = Field(default_factory=list)
    financials: list[FinancialMetric] = Field(default_factory=list)

    # Valuation
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    ps_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ev_ebitda: Optional[float] = None

    # Valuation cases
    valuation_cases: list[ValuationCase] = Field(default_factory=list)
    valuation_chart_url: Optional[str] = None

    # Competition
    competitors: list[CompetitorInfo] = Field(default_factory=list)

    # Catalysts and risks
    catalysts: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)

    # Management signals (v5+)
    management_signals: Optional[dict] = None

    generated_at: datetime = Field(default_factory=datetime.now)


class RepresentativeStock(BaseModel):
    """Representative stock for theme analysis."""

    ticker: str
    name: str
    market_cap: str
    business: str
    position: str  # Position in supply chain
    view: str  # Investment view


class SupplyChainLayer(BaseModel):
    """Supply chain layer."""

    position: str  # upstream, midstream, downstream
    segment: str
    companies: str
    notes: str


class ThemeDriver(BaseModel):
    """Theme driver."""

    title: str
    description: str


class Article3Evidence(BaseModel):
    """Evidence Pack for Article 3 (Theme/Sector)."""

    date: date
    theme: str
    theme_display: str

    # Why now
    why_now: str

    # Drivers
    drivers: list[ThemeDriver] = Field(default_factory=list)

    # Supply chain
    supply_chain_overview: str
    supply_chain: list[SupplyChainLayer] = Field(default_factory=list)
    supply_chain_chart_url: Optional[str] = None

    # Representative stocks
    representative_stocks: list[RepresentativeStock] = Field(default_factory=list)

    # Outlook cases
    bull_case: str
    base_case: str
    bear_case: str

    # Investment strategy
    investment_strategy: str

    # Upcoming events
    upcoming_events: list[dict] = Field(default_factory=list)

    generated_at: datetime = Field(default_factory=datetime.now)
