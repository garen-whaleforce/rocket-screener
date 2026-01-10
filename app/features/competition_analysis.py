"""Competition analysis enhancement (v8).

Provides deeper competitive analysis for Article 2:
- Peer comparison
- Market share estimates
- Competitive dynamics
"""

import logging
from dataclasses import dataclass
from typing import Optional

from app.ingest.fmp_client import FMPClient

logger = logging.getLogger(__name__)

# Pre-defined peer groups
PEER_GROUPS = {
    "NVDA": ["AMD", "INTC", "AVGO", "QCOM"],
    "AMD": ["NVDA", "INTC", "QCOM", "TXN"],
    "AAPL": ["MSFT", "GOOGL", "AMZN", "META"],
    "MSFT": ["AAPL", "GOOGL", "AMZN", "CRM"],
    "TSLA": ["F", "GM", "RIVN", "LCID"],
    "AMZN": ["MSFT", "GOOGL", "WMT", "COST"],
    "META": ["GOOGL", "SNAP", "PINS", "TTD"],
    "TSM": ["INTC", "GFS", "UMC", "ASML"],
}


@dataclass
class CompetitorMetrics:
    """Detailed competitor metrics."""

    ticker: str
    name: str
    market_cap: float
    revenue_ttm: float
    gross_margin: float
    operating_margin: float
    pe_ratio: Optional[float]
    forward_pe: Optional[float]
    revenue_growth: Optional[float]
    market_share_estimate: Optional[float]


@dataclass
class CompetitivePosition:
    """Company's competitive position analysis."""

    ticker: str
    competitive_advantages: list[str]
    competitive_risks: list[str]
    market_position: str  # leader, challenger, follower, niche
    moat_rating: str  # wide, narrow, none
    key_differentiators: list[str]


def get_peer_group(ticker: str, fmp_client: Optional[FMPClient] = None) -> list[str]:
    """Get peer group for a ticker.

    First tries pre-defined groups, then FMP API.

    Args:
        ticker: Stock ticker
        fmp_client: FMP client for API fallback

    Returns:
        List of peer tickers
    """
    # Try pre-defined first
    if ticker in PEER_GROUPS:
        return PEER_GROUPS[ticker]

    # Try FMP API
    if fmp_client:
        try:
            peers = fmp_client.get_stock_peers(ticker)
            if peers:
                return peers[:5]
        except Exception as e:
            logger.warning(f"Failed to get peers from FMP: {e}")

    # Fallback: empty
    return []


def get_competitor_metrics(
    ticker: str, fmp_client: FMPClient
) -> Optional[CompetitorMetrics]:
    """Get detailed metrics for a competitor.

    Args:
        ticker: Competitor ticker
        fmp_client: FMP client

    Returns:
        Competitor metrics or None
    """
    try:
        profile = fmp_client.get_company_profile(ticker)
        ratios = fmp_client.get_financial_ratios(ticker)
        metrics = fmp_client.get_key_metrics(ticker)

        if not profile:
            return None

        return CompetitorMetrics(
            ticker=ticker,
            name=profile.get("companyName", ticker),
            market_cap=profile.get("mktCap", 0),
            revenue_ttm=metrics.get("revenuePerShareTTM", 0) * profile.get("sharesOutstanding", 0)
            if metrics else 0,
            gross_margin=ratios.get("grossProfitMarginTTM", 0) if ratios else 0,
            operating_margin=ratios.get("operatingProfitMarginTTM", 0) if ratios else 0,
            pe_ratio=ratios.get("peRatioTTM") if ratios else None,
            forward_pe=profile.get("pe") if profile else None,
            revenue_growth=None,  # Would need historical data
            market_share_estimate=None,  # Would need industry data
        )
    except Exception as e:
        logger.error(f"Failed to get metrics for {ticker}: {e}")
        return None


def analyze_competitive_position(
    ticker: str,
    peer_metrics: list[CompetitorMetrics],
    company_metrics: Optional[CompetitorMetrics],
) -> CompetitivePosition:
    """Analyze competitive position based on metrics.

    Args:
        ticker: Target ticker
        peer_metrics: List of peer metrics
        company_metrics: Target company metrics

    Returns:
        Competitive position analysis
    """
    advantages = []
    risks = []
    differentiators = []

    if not company_metrics:
        return CompetitivePosition(
            ticker=ticker,
            competitive_advantages=["數據不足"],
            competitive_risks=["需更多資料分析"],
            market_position="unknown",
            moat_rating="unknown",
            key_differentiators=[],
        )

    # Compare to peers
    if peer_metrics:
        avg_margin = sum(p.gross_margin for p in peer_metrics) / len(peer_metrics)
        avg_mcap = sum(p.market_cap for p in peer_metrics) / len(peer_metrics)

        # Margin advantage
        if company_metrics.gross_margin > avg_margin * 1.1:
            advantages.append("毛利率優於同業")
            differentiators.append("定價能力強")
        elif company_metrics.gross_margin < avg_margin * 0.9:
            risks.append("毛利率低於同業平均")

        # Scale advantage
        if company_metrics.market_cap > avg_mcap * 2:
            advantages.append("市值規模領先")
            differentiators.append("規模經濟")

        # Determine position
        if company_metrics.market_cap == max(p.market_cap for p in peer_metrics):
            market_position = "leader"
            moat_rating = "wide" if company_metrics.gross_margin > avg_margin * 1.2 else "narrow"
        elif company_metrics.market_cap > avg_mcap:
            market_position = "challenger"
            moat_rating = "narrow"
        else:
            market_position = "follower"
            moat_rating = "none"
    else:
        market_position = "unknown"
        moat_rating = "unknown"

    # Default items if lists are empty
    if not advantages:
        advantages = ["品牌認知度", "既有客戶基礎"]
    if not risks:
        risks = ["競爭加劇", "技術變遷風險"]
    if not differentiators:
        differentiators = ["產品差異化"]

    return CompetitivePosition(
        ticker=ticker,
        competitive_advantages=advantages,
        competitive_risks=risks,
        market_position=market_position,
        moat_rating=moat_rating,
        key_differentiators=differentiators,
    )


def build_competition_section(
    ticker: str, fmp_client: Optional[FMPClient]
) -> dict:
    """Build complete competition analysis for Article 2.

    Args:
        ticker: Target ticker
        fmp_client: FMP client

    Returns:
        Dict with competition analysis data
    """
    peers = get_peer_group(ticker, fmp_client)
    peer_metrics = []
    company_metrics = None

    if fmp_client:
        company_metrics = get_competitor_metrics(ticker, fmp_client)
        for peer in peers:
            metrics = get_competitor_metrics(peer, fmp_client)
            if metrics:
                peer_metrics.append(metrics)

    position = analyze_competitive_position(ticker, peer_metrics, company_metrics)

    return {
        "peer_group": peers,
        "peer_metrics": [
            {
                "ticker": p.ticker,
                "name": p.name,
                "market_cap": p.market_cap,
                "pe_ratio": p.pe_ratio,
                "gross_margin": p.gross_margin,
            }
            for p in peer_metrics
        ],
        "competitive_position": {
            "advantages": position.competitive_advantages,
            "risks": position.competitive_risks,
            "market_position": position.market_position,
            "moat_rating": position.moat_rating,
            "differentiators": position.key_differentiators,
        },
    }
