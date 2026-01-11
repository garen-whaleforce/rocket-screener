"""Evidence Pack schemas using Pydantic.

Evidence Packs are the single source of truth for article generation.
LLM must only use data from Evidence Packs, never invent numbers.

V2 Fields (optional, for gradual migration):
- Article 1: market_thesis, quick_reads, impact_card, quick_hits, catalyst_calendar, watchlist
- Article 2: tear_sheet, quarterly_financials, sensitivity_matrix, short/medium/long prices
- Article 3: profit_pools, benefit_sequence, extended stock metrics
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
    # v2: support different display formats
    is_rate: bool = False  # True for 10Y yield (display as bps)

    def format_change(self) -> str:
        """Format change for display."""
        sign = "+" if self.change >= 0 else ""
        return f"{sign}{self.change:.2f}"

    def format_change_pct(self) -> str:
        """Format change percent for display."""
        sign = "+" if self.change_pct >= 0 else ""
        return f"{sign}{self.change_pct:.2f}%"

    def format_change_display(self) -> str:
        """Format change for v2 display (bps for rates, % for others)."""
        if self.is_rate:
            bps = self.change * 100  # Convert to basis points
            sign = "+" if bps >= 0 else ""
            return f"{sign}{bps:.1f} bps"
        return self.format_change_pct()


# ============================================================
# Article 1 v2 Models
# ============================================================

class ImpactCard(BaseModel):
    """Impact card for v2 event analysis."""

    beneficiaries: str = ""  # 受益股
    losers: str = ""  # 受害股
    pricing_path: str = ""  # 定價路徑
    key_kpis: str = ""  # 關鍵 KPI


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
    # v2 fields
    price_reaction: Optional[str] = None  # e.g., "NVDA +3.2% 盤後"
    impact_card: Optional[ImpactCard] = None


class QuickHit(BaseModel):
    """Quick hit for v2 (short news item)."""

    summary: str
    ticker: str
    change: Optional[str] = None  # e.g., "+2.3%"


class CatalystEvent(BaseModel):
    """Catalyst event for v2 calendar."""

    time: str  # e.g., "08:30 ET" or "盤後"
    event: str
    ticker: Optional[str] = None
    timing: Optional[str] = None  # "盤前" / "盤後" for earnings


class WatchlistItem(BaseModel):
    """Watchlist item for v2."""

    ticker: str
    reason: str
    key_levels: str  # e.g., "支撐 $150 / 壓力 $165"
    event_time: Optional[str] = None


class Article1Evidence(BaseModel):
    """Evidence Pack for Article 1 (Daily Brief)."""

    date: date
    market_snapshot: list[MarketSnapshotItem]
    top_events: list[TopEvent]
    watch_tonight: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)

    # v2 fields (optional for backward compatibility)
    market_thesis: Optional[str] = None  # 1-2 句今日主線
    quick_reads: list[str] = Field(default_factory=list)  # 格式化三行快讀
    quick_hits: list[QuickHit] = Field(default_factory=list)  # 10-15 則快訊
    catalyst_econ: list[CatalystEvent] = Field(default_factory=list)  # 經濟數據
    catalyst_earnings: list[CatalystEvent] = Field(default_factory=list)  # 財報
    catalyst_other: list[CatalystEvent] = Field(default_factory=list)  # 其他事件
    watchlist: list[WatchlistItem] = Field(default_factory=list)  # 3-7 檔關注
    market_data_timestamp: Optional[str] = None  # 市場資料時間戳

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


# ============================================================
# Article 2 v2 Models
# ============================================================

class ValuationCase(BaseModel):
    """Valuation case (Bull/Base/Bear)."""

    scenario: str  # "bull", "base", "bear"
    assumption: str
    target_price: float
    upside_pct: float
    key_drivers: list[str] = Field(default_factory=list)
    # v2 fields: numerical assumptions
    rev_growth: Optional[str] = None  # e.g., "+15%"
    margin: Optional[str] = None  # e.g., "35%"
    multiple: Optional[str] = None  # e.g., "25x P/E"


class FinancialMetric(BaseModel):
    """Financial metric with period comparison."""

    name: str
    current: str
    previous: Optional[str] = None
    yoy_change: Optional[str] = None


class QuarterlyFinancial(BaseModel):
    """Quarterly financial data for 8Q trend."""

    quarter: str  # e.g., "Q3'24"
    revenue: Optional[str] = None
    revenue_yoy: Optional[str] = None
    gross_margin: Optional[str] = None
    op_margin: Optional[str] = None
    eps: Optional[str] = None


class SensitivityCell(BaseModel):
    """Single cell in sensitivity matrix."""

    eps: float
    multiple: float
    target_price: float


class CompetitorInfo(BaseModel):
    """Competitor information."""

    ticker: str
    name: str
    market_cap: str
    pe_ratio: Optional[float] = None
    revenue_growth: Optional[str] = None
    # v2 fields
    gross_margin: Optional[str] = None
    op_margin: Optional[str] = None
    ev_sales: Optional[float] = None
    moat: Optional[str] = None  # e.g., "規模經濟"


class TargetPrice(BaseModel):
    """Target price for different time horizons."""

    timeframe: str  # "short", "medium", "long"
    method: str  # e.g., "技術面", "NTM EPS × 倍數", "DCF"
    price: float
    rationale: str


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

    # Price info (with data timestamp)
    current_price: float
    price_change_1d: float
    price_change_5d: Optional[float] = None
    price_change_1m: Optional[float] = None
    price_change_3m: Optional[float] = None
    price_52w_high: Optional[float] = None
    price_52w_low: Optional[float] = None
    price_data_as_of: Optional[str] = None  # e.g., "2026/01/10 收盤"
    market_closed: bool = False  # True if market was closed (weekend/holiday)

    # Additional metrics
    beta: Optional[float] = None
    eps_ttm: Optional[float] = None
    roe: Optional[float] = None
    fcf_yield: Optional[float] = None

    # Financial metrics
    key_metrics: list[FinancialMetric] = Field(default_factory=list)
    financials: list[FinancialMetric] = Field(default_factory=list)

    # Valuation
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    ps_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ev_ebitda: Optional[float] = None
    ev: Optional[float] = None  # Enterprise Value
    fcf_ttm: Optional[float] = None  # Free Cash Flow TTM
    div_yield: Optional[float] = None  # Dividend Yield

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

    # ========== v2 fields ==========

    # Investment summary
    investment_summary: Optional[str] = None

    # Tear sheet fields
    after_hours_price: Optional[str] = None  # e.g., "$152.30 盤後"
    ytd_return: Optional[str] = None
    avg_volume_20d: Optional[str] = None
    net_debt: Optional[float] = None  # Negative = net cash
    ntm_pe: Optional[float] = None
    ev_sales: Optional[float] = None
    next_earnings_date: Optional[str] = None
    ex_div_date: Optional[str] = None

    # 8-quarter financials
    quarterly_financials: list[QuarterlyFinancial] = Field(default_factory=list)

    # Cash flow TTM
    ocf_ttm: Optional[str] = None
    capex_ttm: Optional[str] = None

    # Driver analysis
    driver_analysis: Optional[str] = None  # LLM generated

    # Historical averages for comparison
    pe_5y_avg: Optional[float] = None
    ps_5y_avg: Optional[float] = None
    ev_ebitda_5y_avg: Optional[float] = None

    # Peer averages
    pe_peer_avg: Optional[float] = None
    fwd_pe_peer_avg: Optional[float] = None
    ps_peer_avg: Optional[float] = None
    ev_ebitda_peer_avg: Optional[float] = None

    # Sensitivity matrix (5x5)
    sensitivity_eps_range: list[float] = Field(default_factory=list)  # 5 EPS values
    sensitivity_pe_range: list[float] = Field(default_factory=list)  # 5 P/E values
    sensitivity_matrix: list[list[float]] = Field(default_factory=list)  # 5x5 prices

    # Short/Medium/Long term targets
    target_prices: list[TargetPrice] = Field(default_factory=list)

    # What would change my mind
    change_triggers: list[str] = Field(default_factory=list)


# ============================================================
# Article 3 v2 Models
# ============================================================

class RepresentativeStock(BaseModel):
    """Representative stock for theme analysis."""

    ticker: str
    name: str
    market_cap: str
    business: str
    position: str  # Position in supply chain
    view: str  # Investment view
    # v2 fields: performance and valuation
    return_1d: Optional[str] = None
    return_1w: Optional[str] = None
    return_1m: Optional[str] = None
    return_ytd: Optional[str] = None
    vs_spy: Optional[str] = None  # Relative to SPY
    pe: Optional[str] = None
    ev_sales: Optional[str] = None
    ev_ebitda: Optional[str] = None
    rev_growth: Optional[str] = None
    gross_margin: Optional[str] = None
    # Industry-specific KPIs (configurable)
    kpi1: Optional[str] = None
    kpi2: Optional[str] = None
    kpi3: Optional[str] = None


class SupplyChainLayer(BaseModel):
    """Supply chain layer."""

    position: str  # upstream, midstream, downstream
    segment: str
    companies: str
    notes: str


class ProfitPool(BaseModel):
    """Profit pool analysis for v2."""

    position: str  # e.g., "上游", "中游", "下游"
    margin_range: str  # e.g., "40-60%"
    pricing_power: str  # e.g., "強", "中", "弱"
    bottleneck: str  # e.g., "高", "中", "低"
    companies: str


class BenefitStep(BaseModel):
    """Single step in benefit sequence."""

    segment: str
    tickers: str
    trigger: str
    timing: str  # e.g., "立即", "3-6月", "6-12月"


class IndustryKPI(BaseModel):
    """Industry-specific KPI for monitoring."""

    name: str
    description: str
    current: Optional[str] = None


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

    # Representative stocks (with data timestamp)
    representative_stocks: list[RepresentativeStock] = Field(default_factory=list)
    market_cap_as_of: Optional[str] = None  # e.g., "2026/01/10"

    # Outlook cases
    bull_case: str
    base_case: str
    bear_case: str

    # Investment strategy
    investment_strategy: str

    # Upcoming events
    upcoming_events: list[dict] = Field(default_factory=list)

    generated_at: datetime = Field(default_factory=datetime.now)

    # ========== v2 fields ==========

    # Investment thesis (1-2 sentences)
    investment_thesis: Optional[str] = None

    # Profit pool analysis
    profit_pools: list[ProfitPool] = Field(default_factory=list)
    profit_pool_insight: Optional[str] = None

    # Benefit sequence (Who benefits first)
    benefit_pathway: Optional[str] = None  # Description of transmission path
    benefit_sequence: list[BenefitStep] = Field(default_factory=list)

    # Industry-specific KPI names (for dashboard header)
    kpi1_name: Optional[str] = None  # e.g., "交車量" for EV
    kpi2_name: Optional[str] = None
    kpi3_name: Optional[str] = None

    # Scenario trigger conditions
    bull_triggers: list[str] = Field(default_factory=list)
    bear_triggers: list[str] = Field(default_factory=list)
    base_assumptions: list[str] = Field(default_factory=list)

    # First beneficiaries/losers
    bull_beneficiaries: Optional[str] = None
    bear_losers: Optional[str] = None

    # Investment strategy breakdown
    conservative_picks: Optional[str] = None
    conservative_rationale: Optional[str] = None
    growth_picks: Optional[str] = None
    growth_rationale: Optional[str] = None
    aggressive_picks: Optional[str] = None
    aggressive_rationale: Optional[str] = None

    # Industry KPIs for monitoring
    industry_kpis: list[IndustryKPI] = Field(default_factory=list)

    # What would change my mind
    upgrade_conditions: list[str] = Field(default_factory=list)
    downgrade_conditions: list[str] = Field(default_factory=list)
