"""Build Evidence Pack for Article 2 (Stock Deep Dive)."""

import logging
from datetime import date
from typing import Optional

from app.evidence.schemas import (
    Article2Evidence,
    CompetitorInfo,
    FinancialMetric,
    ValuationCase,
)
from app.features.hot_stock_scoring import HotStockCandidate
from app.ingest.fmp_client import FMPClient

logger = logging.getLogger(__name__)


def format_market_cap(value: float) -> str:
    """Format market cap in billions/millions."""
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    elif value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    elif value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    return f"${value:,.0f}"


def calculate_valuation_cases(
    current_price: float,
    pe_ratio: Optional[float],
    forward_pe: Optional[float],
    eps: Optional[float],
) -> list[ValuationCase]:
    """Calculate Bull/Base/Bear valuation cases.

    Uses forward P/E method when available.
    """
    cases = []

    if not forward_pe or not eps:
        # Simplified fallback
        cases = [
            ValuationCase(
                scenario="bear",
                assumption="成長放緩、倍數收縮",
                target_price=current_price * 0.8,
                upside_pct=-20.0,
                key_drivers=["競爭加劇", "需求放緩"],
            ),
            ValuationCase(
                scenario="base",
                assumption="維持現有成長軌跡",
                target_price=current_price * 1.0,
                upside_pct=0.0,
                key_drivers=["穩定成長", "市場預期"],
            ),
            ValuationCase(
                scenario="bull",
                assumption="加速成長、倍數擴張",
                target_price=current_price * 1.25,
                upside_pct=25.0,
                key_drivers=["市場份額提升", "新產品貢獻"],
            ),
        ]
    else:
        # Forward P/E based valuation
        bear_pe = forward_pe * 0.75
        base_pe = forward_pe
        bull_pe = forward_pe * 1.25

        bear_price = bear_pe * eps
        base_price = base_pe * eps
        bull_price = bull_pe * eps

        cases = [
            ValuationCase(
                scenario="bear",
                assumption=f"Forward P/E 收縮至 {bear_pe:.0f}x",
                target_price=bear_price,
                upside_pct=((bear_price / current_price) - 1) * 100,
                key_drivers=["估值收縮", "成長不如預期"],
            ),
            ValuationCase(
                scenario="base",
                assumption=f"維持 Forward P/E {base_pe:.0f}x",
                target_price=base_price,
                upside_pct=((base_price / current_price) - 1) * 100,
                key_drivers=["符合市場預期"],
            ),
            ValuationCase(
                scenario="bull",
                assumption=f"Forward P/E 擴張至 {bull_pe:.0f}x",
                target_price=bull_price,
                upside_pct=((bull_price / current_price) - 1) * 100,
                key_drivers=["超預期成長", "估值擴張"],
            ),
        ]

    return cases


def build_article2_evidence(
    target_date: date,
    fmp_client: Optional[FMPClient],
    hot_stock: HotStockCandidate,
) -> Article2Evidence:
    """Build complete Article 2 Evidence Pack.

    Args:
        target_date: Date for the article
        fmp_client: FMP client
        hot_stock: Selected hot stock

    Returns:
        Article2Evidence ready for rendering
    """
    ticker = hot_stock.ticker

    # Get company data
    profile = None
    quote = None
    ratios = None
    metrics = None
    income = []
    peers = []

    if fmp_client:
        try:
            profile = fmp_client.get_company_profile(ticker)
            quote = fmp_client.get_quote(ticker)
            ratios = fmp_client.get_financial_ratios(ticker)
            metrics = fmp_client.get_key_metrics(ticker)
            income = fmp_client.get_income_statement(ticker, limit=2)
            peers = fmp_client.get_stock_peers(ticker)[:5]
        except Exception as e:
            logger.error(f"Failed to get data for {ticker}: {e}")

    # Extract data with fallbacks
    company_name = profile.get("companyName", ticker) if profile else hot_stock.name
    sector = profile.get("sector", "Technology") if profile else "Technology"
    industry = profile.get("industry", "N/A") if profile else "N/A"
    exchange = profile.get("exchangeShortName", "NASDAQ") if profile else "NASDAQ"
    market_cap = profile.get("mktCap", 0) if profile else 0
    description = profile.get("description", "") if profile else ""

    current_price = quote.get("price", 0) if quote else 0
    price_change_1d = quote.get("changesPercentage", 0) if quote else hot_stock.price_change_pct

    # Valuation metrics
    pe_ratio = ratios.get("peRatioTTM") if ratios else None
    forward_pe = quote.get("pe") if quote else None
    ps_ratio = ratios.get("priceToSalesRatioTTM") if ratios else None
    pb_ratio = ratios.get("priceToBookRatioTTM") if ratios else None
    ev_ebitda = ratios.get("enterpriseValueOverEBITDATTM") if ratios else None
    eps = metrics.get("netIncomePerShareTTM") if metrics else None

    # Build key metrics
    key_metrics = []
    if metrics:
        if metrics.get("revenuePerShareTTM"):
            key_metrics.append(
                FinancialMetric(
                    name="營收/股 (TTM)",
                    current=f"${metrics['revenuePerShareTTM']:.2f}",
                )
            )
        if metrics.get("netIncomePerShareTTM"):
            key_metrics.append(
                FinancialMetric(
                    name="EPS (TTM)",
                    current=f"${metrics['netIncomePerShareTTM']:.2f}",
                )
            )
        if metrics.get("freeCashFlowPerShareTTM"):
            key_metrics.append(
                FinancialMetric(
                    name="FCF/股 (TTM)",
                    current=f"${metrics['freeCashFlowPerShareTTM']:.2f}",
                )
            )

    # Build financials from income statement
    financials = []
    if len(income) >= 2:
        current_q = income[0]
        prev_q = income[1]

        rev_curr = current_q.get("revenue", 0)
        rev_prev = prev_q.get("revenue", 0)
        rev_yoy = ((rev_curr / rev_prev) - 1) * 100 if rev_prev else 0

        financials.append(
            FinancialMetric(
                name="營收",
                current=format_market_cap(rev_curr),
                previous=format_market_cap(rev_prev),
                yoy_change=f"{rev_yoy:+.1f}%",
            )
        )

        gm_curr = current_q.get("grossProfitRatio", 0) * 100
        gm_prev = prev_q.get("grossProfitRatio", 0) * 100
        financials.append(
            FinancialMetric(
                name="毛利率",
                current=f"{gm_curr:.1f}%",
                previous=f"{gm_prev:.1f}%",
                yoy_change=f"{gm_curr - gm_prev:+.1f}pp",
            )
        )

        ni_curr = current_q.get("netIncome", 0)
        ni_prev = prev_q.get("netIncome", 0)
        ni_yoy = ((ni_curr / ni_prev) - 1) * 100 if ni_prev else 0
        financials.append(
            FinancialMetric(
                name="淨利",
                current=format_market_cap(ni_curr),
                previous=format_market_cap(ni_prev),
                yoy_change=f"{ni_yoy:+.1f}%",
            )
        )

    # Build competitor info
    competitors = []
    if fmp_client and peers:
        for peer_ticker in peers[:4]:
            try:
                peer_profile = fmp_client.get_company_profile(peer_ticker)
                peer_ratios = fmp_client.get_financial_ratios(peer_ticker)
                if peer_profile:
                    competitors.append(
                        CompetitorInfo(
                            ticker=peer_ticker,
                            name=peer_profile.get("companyName", peer_ticker),
                            market_cap=format_market_cap(peer_profile.get("mktCap", 0)),
                            pe_ratio=peer_ratios.get("peRatioTTM") if peer_ratios else None,
                            revenue_growth="--",  # Would need historical data
                        )
                    )
            except Exception:
                continue

    # Calculate valuation cases
    valuation_cases = calculate_valuation_cases(
        current_price, pe_ratio, forward_pe, eps
    )

    # Default catalysts and risks
    catalysts = [
        "新產品發布或業務拓展",
        "財報超預期",
        "產業趨勢受惠",
    ]
    risks = [
        "總體經濟衰退風險",
        "競爭加劇",
        "估值過高風險",
    ]

    return Article2Evidence(
        date=target_date,
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        industry=industry,
        exchange=exchange,
        market_cap=format_market_cap(market_cap),
        description=description[:500] if description else "公司資料待補充。",
        current_price=current_price,
        price_change_1d=price_change_1d,
        key_metrics=key_metrics,
        financials=financials,
        pe_ratio=pe_ratio,
        forward_pe=forward_pe,
        ps_ratio=ps_ratio,
        pb_ratio=pb_ratio,
        ev_ebitda=ev_ebitda,
        valuation_cases=valuation_cases,
        competitors=competitors,
        catalysts=catalysts,
        risks=risks,
    )
