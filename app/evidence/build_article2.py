"""Build Evidence Pack for Article 2 (Stock Deep Dive)."""

import logging
from datetime import date, datetime
from typing import Optional

from app.evidence.schemas import (
    Article2Evidence,
    CompetitorInfo,
    FinancialMetric,
    QuarterlyFinancial,
    TargetPrice,
    ValuationCase,
)
from app.features.hot_stock_scoring import HotStockCandidate
from app.ingest.fmp_client import FMPClient

logger = logging.getLogger(__name__)


def get_last_trading_day(target_date: date) -> tuple[date, bool]:
    """Get last trading day and whether market was closed.

    Args:
        target_date: The target date

    Returns:
        Tuple of (last_trading_day, market_was_closed)
    """
    # Simple weekend check (doesn't account for holidays)
    weekday = target_date.weekday()
    if weekday == 5:  # Saturday
        return target_date - __import__('datetime').timedelta(days=1), True
    elif weekday == 6:  # Sunday
        return target_date - __import__('datetime').timedelta(days=2), True
    return target_date, False


def truncate_at_sentence(text: str, max_len: int) -> str:
    """Truncate text at sentence boundary, not mid-word."""
    if len(text) <= max_len:
        return text

    # Find the last sentence boundary before max_len
    truncated = text[:max_len]

    # Try to find sentence boundary (. ! ? followed by space or end)
    for end_char in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
        last_pos = truncated.rfind(end_char)
        if last_pos > max_len // 2:  # Don't truncate too early
            return truncated[:last_pos + 1].strip()

    # Fallback: find last space to avoid cutting words
    last_space = truncated.rfind(' ')
    if last_space > max_len // 2:
        return truncated[:last_space].strip() + "..."

    return truncated.strip() + "..."


def format_market_cap(value: float) -> str:
    """Format market cap in billions/millions. Handles negative values correctly."""
    abs_value = abs(value)
    sign = "-" if value < 0 else ""

    if abs_value >= 1_000_000_000_000:
        return f"{sign}${abs_value / 1_000_000_000_000:.2f}T"
    elif abs_value >= 1_000_000_000:
        return f"{sign}${abs_value / 1_000_000_000:.1f}B"
    elif abs_value >= 1_000_000:
        return f"{sign}${abs_value / 1_000_000:.1f}M"
    elif abs_value >= 1_000:
        return f"{sign}${abs_value / 1_000:.1f}K"
    return f"{sign}${abs_value:,.0f}"


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
        # Simplified fallback - calculate actual upside from target prices
        bear_price = round(current_price * 0.8, 2)
        base_price = round(current_price * 1.01, 2)  # Small upside for base case
        bull_price = round(current_price * 1.25, 2)

        cases = [
            ValuationCase(
                scenario="bear",
                assumption="成長放緩、倍數收縮",
                target_price=bear_price,
                upside_pct=round(((bear_price / current_price) - 1) * 100, 1),
                key_drivers=["競爭加劇", "需求放緩"],
            ),
            ValuationCase(
                scenario="base",
                assumption="維持現有成長軌跡",
                target_price=base_price,
                upside_pct=round(((base_price / current_price) - 1) * 100, 1),
                key_drivers=["穩定成長", "市場預期"],
            ),
            ValuationCase(
                scenario="bull",
                assumption="加速成長、倍數擴張",
                target_price=bull_price,
                upside_pct=round(((bull_price / current_price) - 1) * 100, 1),
                key_drivers=["市場份額提升", "新產品貢獻"],
            ),
        ]
    else:
        # Forward P/E based valuation
        bear_pe = forward_pe * 0.75
        base_pe = forward_pe
        bull_pe = forward_pe * 1.25

        bear_price = round(bear_pe * eps, 2)
        base_price = round(base_pe * eps, 2)
        bull_price = round(bull_pe * eps, 2)

        cases = [
            ValuationCase(
                scenario="bear",
                assumption=f"Forward P/E 收縮至 {bear_pe:.0f}x",
                target_price=bear_price,
                upside_pct=round(((bear_price / current_price) - 1) * 100, 1),
                key_drivers=["估值收縮", "成長不如預期"],
            ),
            ValuationCase(
                scenario="base",
                assumption=f"維持 Forward P/E {base_pe:.0f}x",
                target_price=base_price,
                upside_pct=round(((base_price / current_price) - 1) * 100, 1),
                key_drivers=["符合市場預期"],
            ),
            ValuationCase(
                scenario="bull",
                assumption=f"Forward P/E 擴張至 {bull_pe:.0f}x",
                target_price=bull_price,
                upside_pct=round(((bull_price / current_price) - 1) * 100, 1),
                key_drivers=["超預期成長", "估值擴張"],
            ),
        ]

    return cases


# ============================================================
# V2 Helper Functions
# ============================================================

def build_quarterly_financials(income: list) -> list[QuarterlyFinancial]:
    """Build 8-quarter financials trend.

    Args:
        income: List of income statements (newest first, up to 8 quarters)

    Returns:
        List of QuarterlyFinancial objects
    """
    quarters = []

    for i, q in enumerate(income[:8]):
        period = q.get("period", "")
        year = str(q.get("calendarYear", ""))[-2:]  # Get last 2 digits
        quarter_label = f"{period}'{year}" if period and year else f"Q{i+1}"

        revenue = q.get("revenue", 0)
        gross_profit = q.get("grossProfit", 0)
        operating_income = q.get("operatingIncome", 0)
        eps = q.get("eps", 0)

        # Calculate margins
        gm = (gross_profit / revenue * 100) if revenue else 0
        opm = (operating_income / revenue * 100) if revenue else 0

        # Calculate YoY if we have Q-4 data
        rev_yoy = None
        if i + 4 < len(income):
            prev_rev = income[i + 4].get("revenue", 0)
            if prev_rev and prev_rev > 0:
                rev_yoy = f"{((revenue / prev_rev) - 1) * 100:+.1f}%"

        quarters.append(
            QuarterlyFinancial(
                quarter=quarter_label,
                revenue=format_market_cap(revenue) if revenue else None,
                revenue_yoy=rev_yoy,
                gross_margin=f"{gm:.1f}%" if gm else None,
                op_margin=f"{opm:.1f}%" if opm else None,
                eps=f"${eps:.2f}" if eps else None,
            )
        )

    return quarters


def calculate_sensitivity_matrix(
    current_price: float,
    eps_ttm: Optional[float],
    pe_ratio: Optional[float],
    forward_pe: Optional[float],
) -> tuple[list[float], list[float], list[list[float]]]:
    """Calculate valuation sensitivity matrix (5x5).

    Args:
        current_price: Current stock price
        eps_ttm: TTM EPS
        pe_ratio: Current P/E ratio
        forward_pe: Forward P/E ratio

    Returns:
        Tuple of (eps_range, pe_range, matrix)
    """
    if not eps_ttm or eps_ttm <= 0:
        return [], [], []

    # Use forward P/E as base, fall back to trailing P/E
    base_pe = forward_pe or pe_ratio or (current_price / eps_ttm if eps_ttm > 0 else 20)

    # EPS range: ±20% from current
    eps_range = [
        round(eps_ttm * 0.8, 2),
        round(eps_ttm * 0.9, 2),
        round(eps_ttm, 2),
        round(eps_ttm * 1.1, 2),
        round(eps_ttm * 1.2, 2),
    ]

    # P/E range: centered around base P/E
    pe_range = [
        round(base_pe * 0.7, 1),
        round(base_pe * 0.85, 1),
        round(base_pe, 1),
        round(base_pe * 1.15, 1),
        round(base_pe * 1.3, 1),
    ]

    # Build matrix
    matrix = []
    for eps in eps_range:
        row = []
        for pe in pe_range:
            target_price = round(eps * pe, 2)
            row.append(target_price)
        matrix.append(row)

    return eps_range, pe_range, matrix


def calculate_target_prices(
    current_price: float,
    price_52w_high: Optional[float],
    price_52w_low: Optional[float],
    valuation_cases: list[ValuationCase],
) -> list[TargetPrice]:
    """Calculate short/medium/long term target prices.

    Args:
        current_price: Current stock price
        price_52w_high: 52-week high
        price_52w_low: 52-week low
        valuation_cases: Bull/Base/Bear valuation cases

    Returns:
        List of TargetPrice objects for different time horizons
    """
    targets = []

    # Short-term (1-4 weeks): Technical levels
    if price_52w_high and price_52w_low:
        # Use Fibonacci-like levels
        range_size = price_52w_high - price_52w_low
        support = price_52w_low + range_size * 0.382
        resistance = price_52w_low + range_size * 0.618

        if current_price < resistance:
            short_target = round(resistance, 2)
            rationale = f"短期壓力區 ${resistance:.0f}，支撐 ${support:.0f}"
        else:
            short_target = round(price_52w_high, 2)
            rationale = f"挑戰 52 週高點 ${price_52w_high:.0f}"

        targets.append(
            TargetPrice(
                timeframe="short",
                method="技術面",
                price=short_target,
                rationale=rationale,
            )
        )

    # Medium-term (3-6 months): Base case valuation
    base_case = next((c for c in valuation_cases if c.scenario == "base"), None)
    if base_case:
        targets.append(
            TargetPrice(
                timeframe="medium",
                method="NTM EPS × 倍數",
                price=base_case.target_price,
                rationale=base_case.assumption,
            )
        )

    # Long-term (12-24 months): Bull case valuation
    bull_case = next((c for c in valuation_cases if c.scenario == "bull"), None)
    if bull_case:
        targets.append(
            TargetPrice(
                timeframe="long",
                method="成長假設",
                price=bull_case.target_price,
                rationale=bull_case.assumption,
            )
        )

    return targets


def build_article2_evidence(
    target_date: date,
    fmp_client: Optional[FMPClient],
    hot_stock: HotStockCandidate,
    transcript_config=None,
) -> Article2Evidence:
    """Build complete Article 2 Evidence Pack.

    Args:
        target_date: Date for the article
        fmp_client: FMP client
        hot_stock: Selected hot stock
        transcript_config: Optional transcript API config

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

    balance_sheet = []
    cash_flow = []

    if fmp_client:
        try:
            profile = fmp_client.get_company_profile(ticker)
            quote = fmp_client.get_quote(ticker)
            ratios = fmp_client.get_financial_ratios(ticker)
            metrics = fmp_client.get_key_metrics(ticker)
            # Fetch 8 quarters for true YoY calculation (current Q vs Q-4)
            income = fmp_client.get_income_statement(ticker, limit=8)
            # Fetch balance sheet and cash flow for ROE, D/E, FCF calculations
            balance_sheet = fmp_client.get_balance_sheet(ticker, limit=4)
            cash_flow = fmp_client.get_cash_flow(ticker, limit=4)
            peers = fmp_client.get_stock_peers(ticker)[:5]
        except Exception as e:
            logger.error(f"Failed to get data for {ticker}: {e}")

    # Extract data with fallbacks
    company_name = profile.get("companyName", ticker) if profile else hot_stock.name
    sector = profile.get("sector", "Technology") if profile else "Technology"
    industry = profile.get("industry", "N/A") if profile else "N/A"

    # Exchange: prefer quote.exchange over profile.exchangeShortName (more reliable)
    exchange = "NASDAQ"  # default
    if quote and quote.get("exchange"):
        exchange = quote.get("exchange", "NASDAQ")
    elif profile and profile.get("exchangeShortName"):
        exchange = profile.get("exchangeShortName", "NASDAQ")

    description = profile.get("description", "") if profile else ""

    # Market cap: try profile first, then quote as fallback
    market_cap = 0
    if profile and profile.get("mktCap"):
        market_cap = profile.get("mktCap", 0)
    elif quote and quote.get("marketCap"):
        market_cap = quote.get("marketCap", 0)

    # If still 0, try to calculate from price * sharesOutstanding
    if market_cap == 0 and quote:
        price = quote.get("price", 0)
        shares = quote.get("sharesOutstanding", 0)
        if price and shares:
            market_cap = price * shares
            logger.info(f"Calculated market cap for {ticker}: {market_cap}")

    current_price = quote.get("price", 0) if quote else 0

    # Get 1D change - use API value, fallback to hot_stock if API returns 0
    price_change_1d = quote.get("changesPercentage", 0) if quote else 0

    # If API returns 0 or very small value, likely stale data - use hot_stock value
    if abs(price_change_1d) < 0.01 and hot_stock.price_change_pct != 0:
        price_change_1d = hot_stock.price_change_pct
        logger.info(f"Using hot_stock price_change_pct for {ticker}: {price_change_1d:.2f}%")

    # Fetch 52-week high/low and additional price metrics
    price_52w_high = None
    price_52w_low = None
    price_change_1m = None
    price_change_3m = None
    beta = None

    if fmp_client:
        try:
            # Get historical data for 52-week high/low (1 year back)
            from datetime import timedelta
            one_year_ago = target_date - timedelta(days=365)
            hist = fmp_client.get_historical_price(ticker, from_date=one_year_ago, to_date=target_date)
            if hist and len(hist) > 0:
                # FMP returns data newest first, so prices[0] is most recent
                prices = [d.get("close", 0) for d in hist if d.get("close") and d.get("close") > 0]
                if prices and len(prices) > 20:
                    price_52w_high = max(prices)
                    price_52w_low = min(prices)
                    logger.info(f"52W range for {ticker}: ${price_52w_low:.2f} - ${price_52w_high:.2f}")
                    # Calculate returns: prices[0] is today, prices[N] is N days ago
                    if len(prices) >= 22:
                        price_change_1m = ((current_price / prices[21]) - 1) * 100
                    if len(prices) >= 64:
                        price_change_3m = ((current_price / prices[63]) - 1) * 100
        except Exception as e:
            logger.warning(f"Historical price fetch failed for {ticker}: {e}")

        # Get beta from profile or key metrics
        if profile and profile.get("beta"):
            beta = profile.get("beta")
        elif metrics and metrics.get("beta"):
            beta = metrics.get("beta")

    # Detect market closed (weekend) and get data timestamp with source
    last_trading_day, market_closed = get_last_trading_day(target_date)
    if market_closed:
        price_data_as_of = f"{last_trading_day.strftime('%Y/%m/%d')} 美東收盤（週末休市，來源：FMP API）"
        logger.info(f"Market was closed on {target_date}, using data from {last_trading_day}")
    else:
        price_data_as_of = f"{target_date.strftime('%Y/%m/%d')} 美東收盤（來源：FMP API）"

    # Valuation metrics
    pe_ratio = ratios.get("peRatioTTM") if ratios else None
    # Forward P/E: try metrics endpoint first (more reliable), then quote as fallback
    forward_pe = None
    if metrics and metrics.get("forwardPERatioTTM"):
        forward_pe = metrics.get("forwardPERatioTTM")
    elif quote and quote.get("pe") and quote.get("pe") != pe_ratio:
        # Use quote.pe only if different from trailing P/E (might be forward)
        forward_pe = quote.get("pe")
    ps_ratio = ratios.get("priceToSalesRatioTTM") if ratios else None
    pb_ratio = ratios.get("priceToBookRatioTTM") if ratios else None
    ev_ebitda = ratios.get("enterpriseValueOverEBITDATTM") if ratios else None
    eps = metrics.get("netIncomePerShareTTM") if metrics else None

    # Get additional valuation data: EV, FCF, dividend
    ev = None
    fcf_ttm = None
    div_yield = None
    if metrics:
        ev = metrics.get("enterpriseValueTTM")
        fcf_ttm = metrics.get("freeCashFlowTTM")
    if ratios:
        div_yield = ratios.get("dividendYieldTTM")

    # Build key metrics (with fallback calculations)
    key_metrics = []

    # EPS - try metrics first, then calculate from income statement
    eps_value = None
    if metrics and metrics.get("netIncomePerShareTTM"):
        eps_value = metrics.get("netIncomePerShareTTM")
    elif income and len(income) >= 4:
        # Calculate TTM EPS from last 4 quarters
        ttm_net_income = sum(q.get("netIncome", 0) for q in income[:4])
        shares = income[0].get("weightedAverageShsOutDil", 0)
        if shares and shares > 0:
            eps_value = ttm_net_income / shares

    # P/E fallback: calculate from price/EPS if ratio endpoint is missing
    if pe_ratio is None and eps_value and eps_value > 0.5 and current_price > 0:
        # Only calculate P/E if EPS is meaningfully positive (>$0.50)
        pe_ratio = current_price / eps_value
        logger.info(f"P/E fallback for {ticker}: {pe_ratio:.1f} (from price/EPS ${eps_value:.2f})")
    elif pe_ratio is None and eps_value and eps_value > 0:
        # EPS is positive but very small - log but don't calculate P/E
        logger.info(f"P/E not calculated for {ticker}: EPS ${eps_value:.2f} too small for meaningful ratio")

    if eps_value is not None:
        key_metrics.append(
            FinancialMetric(
                name="EPS (TTM)",
                current=f"${eps_value:.2f}",
            )
        )

    # Revenue per share
    if metrics and metrics.get("revenuePerShareTTM"):
        key_metrics.append(
            FinancialMetric(
                name="營收/股 (TTM)",
                current=f"${metrics['revenuePerShareTTM']:.2f}",
            )
        )

    # FCF per share - try metrics first, then calculate
    fcf_per_share = None
    if metrics and metrics.get("freeCashFlowPerShareTTM"):
        fcf_per_share = metrics.get("freeCashFlowPerShareTTM")

    if fcf_per_share is not None:
        key_metrics.append(
            FinancialMetric(
                name="FCF/股 (TTM)",
                current=f"${fcf_per_share:.2f}",
            )
        )

    # ROE - try ratios first, then calculate from income statement / balance sheet
    roe_value = ratios.get("returnOnEquityTTM") if ratios else None

    # Fallback: calculate ROE from net income / total equity if available
    if roe_value is None and income and len(income) >= 4:
        ttm_net_income = sum(q.get("netIncome", 0) for q in income[:4])
        # Get total stockholders' equity from balance sheet
        total_equity = None
        if balance_sheet and len(balance_sheet) > 0:
            total_equity = balance_sheet[0].get("totalStockholdersEquity")
        # Fallback to book value per share * shares outstanding
        if not total_equity and metrics:
            book_value_per_share = metrics.get("bookValuePerShareTTM", 0)
            shares_out = income[0].get("weightedAverageShsOut", 0)
            if book_value_per_share and shares_out:
                total_equity = book_value_per_share * shares_out
        if total_equity and total_equity > 0 and ttm_net_income:
            roe_value = ttm_net_income / total_equity
            logger.info(f"ROE fallback for {ticker}: {roe_value * 100:.1f}%")

    if roe_value is not None:
        key_metrics.append(
            FinancialMetric(
                name="ROE (TTM)",
                current=f"{roe_value * 100:.1f}%",
            )
        )

    # Net Debt / EBITDA if available
    if metrics:
        net_debt = metrics.get("netDebtTTM")
        if ratios and ratios.get("enterpriseValueOverEBITDATTM") and net_debt:
            # Rough approximation: netDebt/EBITDA ≈ EV/EBITDA * (NetDebt/EV)
            pass  # Complex calculation, skip for now

    # Current Ratio
    if ratios and ratios.get("currentRatioTTM"):
        key_metrics.append(
            FinancialMetric(
                name="流動比率",
                current=f"{ratios['currentRatioTTM']:.2f}x",
            )
        )

    # FCF Yield - calculate and add to KPI (important for valuation)
    fcf_yield_kpi = None
    if metrics and current_price > 0:
        fcf_per_share_val = metrics.get("freeCashFlowPerShareTTM")
        if fcf_per_share_val and fcf_per_share_val != 0:
            fcf_yield_kpi = (fcf_per_share_val / current_price) * 100

    # Fallback: calculate FCF Yield from cash flow statement
    if fcf_yield_kpi is None and cash_flow and len(cash_flow) >= 4 and market_cap > 0:
        # Sum TTM free cash flow
        ttm_fcf = sum(q.get("freeCashFlow", 0) for q in cash_flow[:4])
        if ttm_fcf != 0:
            fcf_yield_kpi = (ttm_fcf / market_cap) * 100
            logger.info(f"FCF Yield fallback for {ticker}: {fcf_yield_kpi:.1f}%")

    if fcf_yield_kpi is not None and fcf_yield_kpi != 0:
        key_metrics.append(
            FinancialMetric(
                name="FCF Yield",
                current=f"{fcf_yield_kpi:.1f}%",
            )
        )

    # Debt to Equity - try multiple sources
    debt_equity_value = None
    if ratios and ratios.get("debtEquityRatioTTM"):
        debt_equity_value = ratios["debtEquityRatioTTM"]
    elif metrics and metrics.get("debtToEquityTTM"):
        debt_equity_value = metrics["debtToEquityTTM"]
    elif balance_sheet and len(balance_sheet) > 0:
        # Calculate from balance sheet
        total_debt = balance_sheet[0].get("totalDebt", 0)
        total_equity_bs = balance_sheet[0].get("totalStockholdersEquity", 0)
        if total_debt and total_equity_bs and total_equity_bs > 0:
            debt_equity_value = total_debt / total_equity_bs
            logger.info(f"D/E fallback for {ticker}: {debt_equity_value:.2f}x")

    if debt_equity_value is not None and debt_equity_value >= 0:
        key_metrics.append(
            FinancialMetric(
                name="負債/權益",
                current=f"{debt_equity_value:.2f}x",
            )
        )

    # Build financials from income statement
    # Use TRUE YoY: compare Q with Q-4 (same quarter last year)
    financials = []
    current_q = income[0] if len(income) >= 1 else None
    # Q-4 for true YoY comparison (same quarter last year)
    yoy_q = income[4] if len(income) >= 5 else None
    # Q-1 for sequential comparison
    prev_q = income[1] if len(income) >= 2 else None

    if current_q:
        # Get current quarter label (e.g., "Q4 2024")
        current_period = current_q.get("period", "")
        fiscal_year = current_q.get("calendarYear", "")
        quarter_label = f"{current_period} {fiscal_year}" if current_period and fiscal_year else "最近一季"

        # Revenue - with true YoY
        rev_curr = current_q.get("revenue", 0)
        rev_yoy_val = yoy_q.get("revenue", 0) if yoy_q else 0
        rev_prev = prev_q.get("revenue", 0) if prev_q else 0

        # Calculate true YoY growth (vs same quarter last year)
        if rev_yoy_val and rev_yoy_val != 0:
            rev_yoy_pct = ((rev_curr / rev_yoy_val) - 1) * 100
            yoy_label = f"{rev_yoy_pct:+.1f}% YoY"
        else:
            yoy_label = "N/A"

        # Also calculate QoQ for reference
        if rev_prev and rev_prev != 0:
            rev_qoq_pct = ((rev_curr / rev_prev) - 1) * 100
            qoq_label = f"({rev_qoq_pct:+.1f}% QoQ)"
        else:
            qoq_label = ""

        financials.append(
            FinancialMetric(
                name=f"營收 ({quarter_label})",
                current=format_market_cap(rev_curr),
                previous=format_market_cap(rev_yoy_val) if yoy_q else "--",
                yoy_change=yoy_label,
            )
        )

        # Gross margin - compare with same quarter last year
        # Some companies (e.g., Visa) don't have grossProfitRatio, calculate from grossProfit/revenue
        gm_curr = current_q.get("grossProfitRatio", 0) * 100
        if gm_curr == 0:
            # Fallback: calculate from grossProfit / revenue
            gross_profit = current_q.get("grossProfit", 0)
            if gross_profit and rev_curr:
                gm_curr = (gross_profit / rev_curr) * 100

        gm_yoy = 0
        if yoy_q:
            gm_yoy = yoy_q.get("grossProfitRatio", 0) * 100
            if gm_yoy == 0:
                gross_profit_yoy = yoy_q.get("grossProfit", 0)
                rev_yoy = yoy_q.get("revenue", 0)
                if gross_profit_yoy and rev_yoy:
                    gm_yoy = (gross_profit_yoy / rev_yoy) * 100

        # Only show gross margin if we have valid data
        if gm_curr > 0:
            if gm_yoy and gm_yoy > 0:
                gm_change = gm_curr - gm_yoy
                gm_yoy_label = f"{gm_change:+.1f}pp YoY"
            else:
                gm_yoy_label = "--"

            financials.append(
                FinancialMetric(
                    name="毛利率",
                    current=f"{gm_curr:.1f}%",
                    previous=f"{gm_yoy:.1f}%" if gm_yoy > 0 else "--",
                    yoy_change=gm_yoy_label,
                )
            )
        else:
            # Skip gross margin entirely if no data (e.g., financial services)
            logger.info(f"Skipping gross margin for {ticker}: no grossProfit data")

        # Net income - with true YoY (handle loss-to-profit scenarios)
        ni_curr = current_q.get("netIncome", 0)
        ni_yoy_val = yoy_q.get("netIncome", 0) if yoy_q else 0

        # Handle special cases for loss/profit transitions
        if ni_yoy_val and ni_yoy_val != 0:
            if ni_yoy_val < 0 and ni_curr > 0:
                # Loss to profit - show as turnaround
                ni_yoy_label = "轉虧為盈"
            elif ni_yoy_val > 0 and ni_curr < 0:
                # Profit to loss - show as turnaround
                ni_yoy_label = "轉盈為虧"
            elif ni_yoy_val < 0 and ni_curr < 0:
                # Both losses - compare improvement
                improvement = ((abs(ni_yoy_val) - abs(ni_curr)) / abs(ni_yoy_val)) * 100
                if improvement > 0:
                    ni_yoy_label = f"虧損收窄 {improvement:.0f}%"
                else:
                    ni_yoy_label = f"虧損擴大 {abs(improvement):.0f}%"
            else:
                # Normal case: both positive
                ni_yoy_pct = ((ni_curr / ni_yoy_val) - 1) * 100
                ni_yoy_label = f"{ni_yoy_pct:+.1f}% YoY"
        else:
            ni_yoy_label = "N/A"

        financials.append(
            FinancialMetric(
                name="淨利",
                current=format_market_cap(ni_curr),
                previous=format_market_cap(ni_yoy_val) if yoy_q else "--",
                yoy_change=ni_yoy_label,
            )
        )

        # Operating income - with true YoY (handle loss-to-profit scenarios)
        oi_curr = current_q.get("operatingIncome", 0)
        oi_yoy_val = yoy_q.get("operatingIncome", 0) if yoy_q else 0

        # Handle special cases for operating income loss/profit transitions
        if oi_curr and oi_yoy_val and oi_yoy_val != 0:
            if oi_yoy_val < 0 and oi_curr > 0:
                oi_yoy_label = "轉虧為盈"
            elif oi_yoy_val > 0 and oi_curr < 0:
                oi_yoy_label = "轉盈為虧"
            elif oi_yoy_val < 0 and oi_curr < 0:
                improvement = ((abs(oi_yoy_val) - abs(oi_curr)) / abs(oi_yoy_val)) * 100
                if improvement > 0:
                    oi_yoy_label = f"虧損收窄 {improvement:.0f}%"
                else:
                    oi_yoy_label = f"虧損擴大 {abs(improvement):.0f}%"
            else:
                oi_yoy_pct = ((oi_curr / oi_yoy_val) - 1) * 100
                oi_yoy_label = f"{oi_yoy_pct:+.1f}% YoY"
        else:
            oi_yoy_label = "N/A"

        if oi_curr:
            financials.append(
                FinancialMetric(
                    name="營業利益",
                    current=format_market_cap(oi_curr),
                    previous=format_market_cap(oi_yoy_val) if yoy_q else "--",
                    yoy_change=oi_yoy_label,
                )
            )

        # Operating margin - calculate from operatingIncome/revenue if ratio is missing
        om_curr = current_q.get("operatingIncomeRatio", 0) * 100
        if om_curr == 0 and oi_curr and rev_curr:
            om_curr = (oi_curr / rev_curr) * 100

        om_yoy = None
        if yoy_q:
            om_yoy = yoy_q.get("operatingIncomeRatio", 0) * 100
            if om_yoy == 0 and oi_yoy_val and rev_yoy_val:
                om_yoy = (oi_yoy_val / rev_yoy_val) * 100

        # Show operating margin even if negative (important for turnaround stocks)
        if om_curr != 0 or (oi_curr and rev_curr):
            # Calculate YoY change in pp (handle negative to positive transition)
            if om_yoy is not None:
                om_change = om_curr - om_yoy
                om_yoy_label = f"{om_change:+.1f}pp YoY"
                om_yoy_display = f"{om_yoy:.1f}%"
            else:
                om_yoy_label = "--"
                om_yoy_display = "--"

            financials.append(
                FinancialMetric(
                    name="營業利益率",
                    current=f"{om_curr:.1f}%",
                    previous=om_yoy_display,
                    yoy_change=om_yoy_label,
                )
            )

        logger.info(f"Built financials for {ticker}: {quarter_label}, YoY comparison available: {yoy_q is not None}")

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

    # Generate catalysts and risks using LLM
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

    # Use LLM to generate better analysis
    from app.llm.client import get_llm_client

    llm_client = get_llm_client()
    if llm_client:
        try:
            financials_for_llm = [
                {"name": f.name, "current": f.current} for f in financials
            ]
            valuation_for_llm = {
                "pe": pe_ratio,
                "forward_pe": forward_pe,
                "ps": ps_ratio,
                "ev_ebitda": ev_ebitda,
            }
            analysis = llm_client.generate_stock_analysis(
                ticker=ticker,
                company_name=company_name,
                description=description[:300] if description else "",
                financials=financials_for_llm,
                valuation=valuation_for_llm,
                price_change=price_change_1d,
            )
            catalysts = analysis.get("catalysts", catalysts)
            risks = analysis.get("risk_factors", risks)
            logger.info(f"LLM generated analysis for {ticker}")
        except Exception as e:
            logger.warning(f"LLM analysis failed for {ticker}: {e}")

    # Fetch management signals from transcript (v5 - LLM enhanced)
    management_signals = None
    if transcript_config:
        try:
            from app.ingest.transcript_client import (
                TranscriptClient,
                get_management_signals,
                extract_with_llm,
            )

            transcript_client = TranscriptClient(transcript_config)

            # Try LLM-enhanced extraction first (v5)
            extract, _ = extract_with_llm(transcript_client, ticker, llm_client)

            if extract:
                # Use enhanced extraction
                from app.llm.extract_transcript_json import get_enhanced_management_signals
                management_signals = get_enhanced_management_signals(extract)
                logger.info(f"LLM transcript extracted for {ticker}: {extract.quarter}")
            else:
                # Fallback to keyword-based extraction
                raw_transcript = transcript_client.get_latest_transcript(ticker)
                if raw_transcript:
                    extract = transcript_client.extract_structured_data(raw_transcript)
                    management_signals = get_management_signals(extract)
                    logger.info(f"Keyword transcript extracted for {ticker}: {extract.quarter if extract else 'N/A'}")
        except Exception as e:
            logger.warning(f"Transcript fetch failed for {ticker}: {e}")

    # Additional metrics from FMP - use calculated values as fallback
    eps_ttm = metrics.get("netIncomePerShareTTM") if metrics else None
    # Fallback: use calculated eps_value if API returns None
    if eps_ttm is None and eps_value is not None:
        eps_ttm = eps_value
        logger.info(f"Using calculated EPS for {ticker}: ${eps_ttm:.2f}")

    roe = ratios.get("returnOnEquityTTM") if ratios else None
    # Fallback: use calculated roe_value
    if roe is None and roe_value is not None:
        roe = roe_value

    fcf_yield = None
    if metrics and current_price > 0:
        fcf_per_share = metrics.get("freeCashFlowPerShareTTM")
        if fcf_per_share:
            fcf_yield = (fcf_per_share / current_price) * 100
    # Fallback: use calculated fcf_yield_kpi
    if fcf_yield is None and fcf_yield_kpi is not None:
        fcf_yield = fcf_yield_kpi

    # Translate company description to Traditional Chinese
    description_zh = description
    if description:
        from app.llm.client import get_llm_client
        llm_client = get_llm_client()
        if llm_client:
            try:
                description_zh = llm_client.translate_company_description(ticker, description)
                logger.info(f"Translated company description for {ticker}")
            except Exception as e:
                logger.warning(f"Failed to translate description for {ticker}: {e}")

    # ========== V2 Fields ==========

    # Build 8-quarter financials trend
    quarterly_financials = build_quarterly_financials(income) if income else []

    # Calculate sensitivity matrix
    sensitivity_eps_range, sensitivity_pe_range, sensitivity_matrix = calculate_sensitivity_matrix(
        current_price, eps_ttm, pe_ratio, forward_pe
    )

    # Calculate target prices
    target_prices = calculate_target_prices(
        current_price, price_52w_high, price_52w_low, valuation_cases
    )

    # Calculate YTD return
    ytd_return = None
    if fmp_client and current_price:
        try:
            from datetime import timedelta
            year_start = date(target_date.year, 1, 1)
            hist = fmp_client.get_historical_price(ticker, from_date=year_start, to_date=year_start + timedelta(days=7))
            if hist and len(hist) > 0:
                # Find first trading day of year
                start_price = hist[-1].get("close", 0)  # Oldest = year start
                if start_price > 0:
                    ytd_return = f"{((current_price / start_price) - 1) * 100:+.1f}%"
        except Exception as e:
            logger.debug(f"YTD calculation failed for {ticker}: {e}")

    # Get next earnings date
    next_earnings_date = None
    if fmp_client:
        try:
            earnings_cal = fmp_client.get_earnings_calendar(ticker)
            if earnings_cal and len(earnings_cal) > 0:
                # Find next upcoming earnings
                for ec in earnings_cal:
                    ec_date = ec.get("date", "")
                    if ec_date >= target_date.isoformat():
                        next_earnings_date = ec_date
                        break
        except Exception:
            pass

    # Get net debt from metrics
    net_debt = metrics.get("netDebtTTM") if metrics else None

    # Get EV/Sales
    ev_sales = None
    if metrics and metrics.get("enterpriseValueTTM") and income and len(income) >= 4:
        ttm_revenue = sum(q.get("revenue", 0) for q in income[:4])
        if ttm_revenue > 0:
            ev_sales = metrics.get("enterpriseValueTTM") / ttm_revenue

    # Generate investment summary via LLM (optional)
    investment_summary = None
    change_triggers = []
    if llm_client:
        try:
            # Simple investment summary based on valuation
            base_case = next((c for c in valuation_cases if c.scenario == "base"), None)
            if base_case:
                upside = base_case.upside_pct
                if upside > 15:
                    investment_summary = f"{company_name}（{ticker}）目前股價 ${current_price:.2f}，基準目標價 ${base_case.target_price:.0f}，具 {upside:.0f}% 上行空間。"
                elif upside > 0:
                    investment_summary = f"{company_name}（{ticker}）目前股價 ${current_price:.2f}，估值合理，基準目標價 ${base_case.target_price:.0f}。"
                else:
                    investment_summary = f"{company_name}（{ticker}）目前股價 ${current_price:.2f}，短期估值偏高，需等待更好切入點。"

            # Change triggers (from risks and catalysts)
            if catalysts:
                change_triggers.append(f"上調條件：{catalysts[0]}")
            if risks:
                change_triggers.append(f"下調條件：{risks[0]}")
        except Exception as e:
            logger.debug(f"Investment summary generation failed: {e}")

    return Article2Evidence(
        date=target_date,
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        industry=industry,
        exchange=exchange,
        market_cap=format_market_cap(market_cap),
        description=truncate_at_sentence(description_zh, 500) if description_zh else "公司資料待補充。",
        current_price=current_price,
        price_change_1d=price_change_1d,
        price_change_1m=price_change_1m,
        price_change_3m=price_change_3m,
        price_52w_high=price_52w_high,
        price_52w_low=price_52w_low,
        price_data_as_of=price_data_as_of,
        market_closed=market_closed,
        beta=beta,
        eps_ttm=eps_ttm,
        roe=roe,
        fcf_yield=fcf_yield,
        key_metrics=key_metrics,
        financials=financials,
        pe_ratio=pe_ratio,
        forward_pe=forward_pe,
        ps_ratio=ps_ratio,
        pb_ratio=pb_ratio,
        ev_ebitda=ev_ebitda,
        ev=ev,
        fcf_ttm=fcf_ttm,
        div_yield=div_yield,
        valuation_cases=valuation_cases,
        competitors=competitors,
        catalysts=catalysts,
        risks=risks,
        management_signals=management_signals,
        # v2 fields
        investment_summary=investment_summary,
        ytd_return=ytd_return,
        net_debt=net_debt,
        ev_sales=ev_sales,
        next_earnings_date=next_earnings_date,
        quarterly_financials=quarterly_financials,
        sensitivity_eps_range=sensitivity_eps_range,
        sensitivity_pe_range=sensitivity_pe_range,
        sensitivity_matrix=sensitivity_matrix,
        target_prices=target_prices,
        change_triggers=change_triggers,
    )
