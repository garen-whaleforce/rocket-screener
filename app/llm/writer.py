"""LLM-based article writer.

Uses Evidence Pack to generate article content.
LLM is ONLY allowed to:
1. Write prose based on Evidence Pack data
2. Infer causation/implications (but not invent numbers)
3. Structure content according to template
"""

import logging
import os
from datetime import date
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from app.evidence.schemas import Article1Evidence, Article2Evidence, Article3Evidence

logger = logging.getLogger(__name__)

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def get_template_env() -> Environment:
    """Get Jinja2 environment with templates."""
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=False,
    )


def render_article1_v2(evidence: Article1Evidence) -> str:
    """Render Article 1 v2 from Evidence Pack using Jinja2 template.

    V2 includes: Market thesis, quick hits, catalyst calendar, watchlist,
    price reactions, and impact cards.
    """
    env = get_template_env()
    try:
        template = env.get_template("article1_v2.md")
    except Exception as e:
        logger.warning(f"Failed to load article1_v2.md template: {e}, falling back to v1")
        return render_article1(evidence)

    date_display = evidence.date.strftime("%Y/%m/%d")

    # Format market snapshot for display
    market_snapshot = []
    for item in evidence.market_snapshot:
        market_snapshot.append({
            "name": item.name,
            "symbol": item.symbol,
            "close": f"{item.close:,.2f}" if item.close else "--",
            "change": item.format_change() if item.close else "--",
            "change_pct": item.format_change_pct() if item.close else "--",
            "change_display": item.format_change_display() if item.close else "--",
        })

    # Prepare template context
    context = {
        "date_display": date_display,
        "market_thesis": evidence.market_thesis or "市場觀望氣氛濃厚，等待關鍵數據與財報。",
        "quick_reads": evidence.quick_reads or [],
        "market_snapshot": market_snapshot,
        "market_data_timestamp": evidence.market_data_timestamp,
        "top_events": evidence.top_events,
        "quick_hits": evidence.quick_hits,
        "catalyst_econ": evidence.catalyst_econ,
        "catalyst_earnings": evidence.catalyst_earnings,
        "catalyst_other": evidence.catalyst_other,
        "watchlist": evidence.watchlist,
        "watch_tonight": evidence.watch_tonight,
    }

    try:
        return template.render(**context)
    except Exception as e:
        logger.warning(f"Failed to render article1_v2 template: {e}, falling back to v1")
        return render_article1(evidence)


def render_article1(evidence: Article1Evidence) -> str:
    """Render Article 1 from Evidence Pack.

    Currently uses template-based rendering.
    Future: LLM enhancement for prose sections.
    """
    date_display = evidence.date.strftime("%Y/%m/%d")

    # Format market snapshot for display
    market_snapshot = []
    for item in evidence.market_snapshot:
        market_snapshot.append({
            "name": item.name,
            "close": f"{item.close:,.2f}" if item.close else "--",
            "change": item.format_change() if item.close else "--",
            "change_pct": item.format_change_pct() if item.close else "--",
        })

    # Generate quick summary
    if evidence.top_events:
        top_3 = evidence.top_events[:3]
        quick_summary = "\n".join([
            f"- {e.headline[:60]}..." if len(e.headline) > 60 else f"- {e.headline}"
            for e in top_3
        ])
    else:
        quick_summary = "- 市場等待重要數據公布"

    # Format events
    top_events = []
    for event in evidence.top_events:
        top_events.append({
            "headline": event.headline,
            "what_happened": event.what_happened,
            "why_important": event.why_important or "市場正在評估此事件的影響。",
            "impact": event.impact or "影響程度待觀察。",
            "next_watch": event.next_watch or "持續關注後續發展。",
            "source_urls": event.source_urls,
        })

    # Build markdown (不含 H1 標題，Ghost 會自動顯示標題)
    lines = [
        f"> {date_display} | 美股蓋倫哥",
        "",
        "---",
        "",
        "## 三行快讀",
        "",
        quick_summary,
        "",
        "---",
        "",
        "## 市場快照",
        "",
        "| 指標 | 收盤 | 漲跌 | 漲跌幅 |",
        "|------|------|------|--------|",
    ]

    for item in market_snapshot:
        lines.append(
            f"| {item['name']} | {item['close']} | {item['change']} | {item['change_pct']} |"
        )

    lines.extend([
        "",
        "---",
        "",
        f"## 今日焦點 Top {len(top_events)}",
        "",
    ])

    for i, event in enumerate(top_events, 1):
        lines.extend([
            f"### {i}. {event['headline']}",
            "",
            "**發生什麼事？**",
            event["what_happened"],
            "",
            "**為何重要？**",
            event["why_important"],
            "",
            "**可能影響**",
            event["impact"],
            "",
            "**下一步觀察**",
            event["next_watch"],
            "",
        ])

        # Source links
        source_links = " | ".join([
            f"[{j}]({url})" for j, url in enumerate(event["source_urls"], 1)
        ])
        lines.extend([
            f"📎 來源：{source_links}",
            "",
            "---",
            "",
        ])

    lines.extend([
        "## 今晚必看",
        "",
    ])
    for item in evidence.watch_tonight:
        lines.append(f"- {item}")

    lines.extend([
        "",
        "---",
        "",
        "## 風險提示",
        "",
        "本文內容僅供參考，不構成任何投資建議。投資有風險，入市需謹慎。過去績效不代表未來表現。",
        "",
        "---",
        "",
        "*Rocket Screener — 獻給散戶的機構級分析*",
    ])

    return "\n".join(lines)


def render_article2_v2(evidence: Article2Evidence) -> str:
    """Render Article 2 v2 from Evidence Pack using Jinja2 template.

    V2 includes: Tear sheet, 8-quarter financials, sensitivity matrix,
    short/medium/long term targets, competitor matrix with moat.
    """
    env = get_template_env()
    try:
        template = env.get_template("article2_v2.md")
    except Exception as e:
        logger.warning(f"Failed to load article2_v2.md template: {e}, falling back to v1")
        return render_article2(evidence)

    date_display = evidence.date.strftime("%Y/%m/%d")

    # Format quarterly financials
    q_labels = []
    q_revenues = []
    q_rev_yoys = []
    q_gms = []
    q_opms = []
    q_epss = []
    for i, q in enumerate(evidence.quarterly_financials[:8]):
        q_labels.append(q.quarter)
        q_revenues.append(q.revenue or "--")
        q_rev_yoys.append(q.revenue_yoy or "--")
        q_gms.append(q.gross_margin or "--")
        q_opms.append(q.op_margin or "--")
        q_epss.append(q.eps or "--")

    # Pad to 8 quarters if needed
    while len(q_labels) < 8:
        q_labels.append(f"Q{len(q_labels)+1}")
        q_revenues.append("--")
        q_rev_yoys.append("--")
        q_gms.append("--")
        q_opms.append("--")
        q_epss.append("--")

    # Format sensitivity matrix
    pe_cols = evidence.sensitivity_pe_range[:5] if evidence.sensitivity_pe_range else [15, 18, 20, 22, 25]
    eps_rows = evidence.sensitivity_eps_range[:5] if evidence.sensitivity_eps_range else []
    sens_matrix = evidence.sensitivity_matrix[:5] if evidence.sensitivity_matrix else []

    # Calculate pct from high/low
    pct_from_high = None
    pct_from_low = None
    if evidence.price_52w_high and evidence.current_price:
        pct_from_high = f"{((evidence.current_price / evidence.price_52w_high) - 1) * 100:+.1f}%"
    if evidence.price_52w_low and evidence.current_price:
        pct_from_low = f"{((evidence.current_price / evidence.price_52w_low) - 1) * 100:+.1f}%"

    # Get target prices
    short_term = next((t for t in evidence.target_prices if t.timeframe == "short"), None)
    medium_term = next((t for t in evidence.target_prices if t.timeframe == "medium"), None)
    long_term = next((t for t in evidence.target_prices if t.timeframe == "long"), None)

    # Format valuation cases
    bull_case = next((c for c in evidence.valuation_cases if c.scenario == "bull"), None)
    base_case = next((c for c in evidence.valuation_cases if c.scenario == "base"), None)
    bear_case = next((c for c in evidence.valuation_cases if c.scenario == "bear"), None)

    # Prepare template context
    context = {
        "date_display": date_display,
        "ticker": evidence.ticker,
        "investment_summary": evidence.investment_summary or f"{evidence.company_name} ({evidence.ticker}) 深度分析報告。",
        # Tear sheet
        "current_price": evidence.current_price,
        "after_hours_price": evidence.after_hours_price or "--",
        "price_52w_high": evidence.price_52w_high,
        "price_52w_low": evidence.price_52w_low,
        "ytd_return": evidence.ytd_return or "--",
        "return_1m": f"{evidence.price_change_1m:+.1f}%" if evidence.price_change_1m else "--",
        "return_3m": f"{evidence.price_change_3m:+.1f}%" if evidence.price_change_3m else "--",
        "beta": f"{evidence.beta:.2f}" if evidence.beta else "--",
        "avg_volume_20d": evidence.avg_volume_20d or "--",
        "market_cap": evidence.market_cap,
        "enterprise_value": f"${evidence.ev/1e9:.1f}B" if evidence.ev else "--",
        "net_debt_or_cash": f"${evidence.net_debt/1e9:.1f}B" if evidence.net_debt else "--",
        "ntm_pe": f"{evidence.ntm_pe:.1f}x" if evidence.ntm_pe else "--",
        "ev_sales": f"{evidence.ev_sales:.1f}x" if evidence.ev_sales else "--",
        "ev_ebitda": f"{evidence.ev_ebitda:.1f}x" if evidence.ev_ebitda else "--",
        "next_earnings_date": evidence.next_earnings_date or "--",
        "ex_div_date": evidence.ex_div_date or "--",
        "data_timestamp": evidence.price_data_as_of or date_display,
        # Company
        "company_description": evidence.description,
        "sector": evidence.sector,
        "industry": evidence.industry,
        "exchange": evidence.exchange,
        # KPIs
        "key_kpis": evidence.key_metrics,
        # 8-quarter financials
        "q1_label": q_labels[0], "q2_label": q_labels[1], "q3_label": q_labels[2], "q4_label": q_labels[3],
        "q5_label": q_labels[4], "q6_label": q_labels[5], "q7_label": q_labels[6], "q8_label": q_labels[7],
        "q1_revenue": q_revenues[0], "q2_revenue": q_revenues[1], "q3_revenue": q_revenues[2], "q4_revenue": q_revenues[3],
        "q5_revenue": q_revenues[4], "q6_revenue": q_revenues[5], "q7_revenue": q_revenues[6], "q8_revenue": q_revenues[7],
        "q1_rev_yoy": q_rev_yoys[0], "q2_rev_yoy": q_rev_yoys[1], "q3_rev_yoy": q_rev_yoys[2], "q4_rev_yoy": q_rev_yoys[3],
        "q5_rev_yoy": q_rev_yoys[4], "q6_rev_yoy": q_rev_yoys[5], "q7_rev_yoy": q_rev_yoys[6], "q8_rev_yoy": q_rev_yoys[7],
        "q1_gm": q_gms[0], "q2_gm": q_gms[1], "q3_gm": q_gms[2], "q4_gm": q_gms[3],
        "q5_gm": q_gms[4], "q6_gm": q_gms[5], "q7_gm": q_gms[6], "q8_gm": q_gms[7],
        "q1_opm": q_opms[0], "q2_opm": q_opms[1], "q3_opm": q_opms[2], "q4_opm": q_opms[3],
        "q5_opm": q_opms[4], "q6_opm": q_opms[5], "q7_opm": q_opms[6], "q8_opm": q_opms[7],
        "q1_eps": q_epss[0], "q2_eps": q_epss[1], "q3_eps": q_epss[2], "q4_eps": q_epss[3],
        "q5_eps": q_epss[4], "q6_eps": q_epss[5], "q7_eps": q_epss[6], "q8_eps": q_epss[7],
        # Cash flow
        "ocf_ttm": evidence.ocf_ttm or "--",
        "ocf_ttm_prev": "--",
        "ocf_yoy": "--",
        "capex_ttm": evidence.capex_ttm or "--",
        "capex_ttm_prev": "--",
        "capex_yoy": "--",
        "fcf_ttm": f"${evidence.fcf_ttm/1e9:.1f}B" if evidence.fcf_ttm else "--",
        "fcf_ttm_prev": "--",
        "fcf_yoy": "--",
        "fcf_yield": f"{evidence.fcf_yield:.1f}%" if evidence.fcf_yield else "--",
        # Driver analysis
        "driver_analysis": evidence.driver_analysis or "請參考財報內容分析營收變動因素。",
        # Momentum
        "price_data_timestamp": evidence.price_data_as_of,
        "price_change_1d": f"{evidence.price_change_1d:+.2f}%",
        "price_change_5d": f"{evidence.price_change_5d:+.2f}%" if evidence.price_change_5d else "--",
        "price_change_1m": f"{evidence.price_change_1m:+.1f}%" if evidence.price_change_1m else "--",
        "price_change_3m": f"{evidence.price_change_3m:+.1f}%" if evidence.price_change_3m else "--",
        "pct_from_high": pct_from_high or "--",
        "pct_from_low": pct_from_low or "--",
        # Competitors
        "competitors": evidence.competitors,
        # Valuation
        "pe_ttm": f"{evidence.pe_ratio:.1f}x" if evidence.pe_ratio else "--",
        "pe_5y_avg": f"{evidence.pe_5y_avg:.1f}x" if evidence.pe_5y_avg else "--",
        "pe_peer_avg": f"{evidence.pe_peer_avg:.1f}x" if evidence.pe_peer_avg else "--",
        "forward_pe": f"{evidence.forward_pe:.1f}x" if evidence.forward_pe else "--",
        "fwd_pe_peer_avg": f"{evidence.fwd_pe_peer_avg:.1f}x" if evidence.fwd_pe_peer_avg else "--",
        "ps_ratio": f"{evidence.ps_ratio:.1f}x" if evidence.ps_ratio else "--",
        "ps_5y_avg": f"{evidence.ps_5y_avg:.1f}x" if evidence.ps_5y_avg else "--",
        "ps_peer_avg": f"{evidence.ps_peer_avg:.1f}x" if evidence.ps_peer_avg else "--",
        "ev_ebitda_5y_avg": f"{evidence.ev_ebitda_5y_avg:.1f}x" if evidence.ev_ebitda_5y_avg else "--",
        "ev_ebitda_peer_avg": f"{evidence.ev_ebitda_peer_avg:.1f}x" if evidence.ev_ebitda_peer_avg else "--",
        # Bull/Base/Bear
        "bear_assumption": bear_case.assumption if bear_case else "--",
        "bear_rev_growth": bear_case.rev_growth if bear_case else "--",
        "bear_margin": bear_case.margin if bear_case else "--",
        "bear_multiple": bear_case.multiple if bear_case else "--",
        "bear_price": bear_case.target_price if bear_case else 0,
        "bear_upside": f"{bear_case.upside_pct:+.1f}%" if bear_case else "--",
        "base_assumption": base_case.assumption if base_case else "--",
        "base_rev_growth": base_case.rev_growth if base_case else "--",
        "base_margin": base_case.margin if base_case else "--",
        "base_multiple": base_case.multiple if base_case else "--",
        "base_price": base_case.target_price if base_case else 0,
        "base_upside": f"{base_case.upside_pct:+.1f}%" if base_case else "--",
        "bull_assumption": bull_case.assumption if bull_case else "--",
        "bull_rev_growth": bull_case.rev_growth if bull_case else "--",
        "bull_margin": bull_case.margin if bull_case else "--",
        "bull_multiple": bull_case.multiple if bull_case else "--",
        "bull_price": bull_case.target_price if bull_case else 0,
        "bull_upside": f"{bull_case.upside_pct:+.1f}%" if bull_case else "--",
        # Sensitivity matrix
        "pe_col1": pe_cols[0] if len(pe_cols) > 0 else 15,
        "pe_col2": pe_cols[1] if len(pe_cols) > 1 else 18,
        "pe_col3": pe_cols[2] if len(pe_cols) > 2 else 20,
        "pe_col4": pe_cols[3] if len(pe_cols) > 3 else 22,
        "pe_col5": pe_cols[4] if len(pe_cols) > 4 else 25,
        "eps_row1": f"{eps_rows[0]:.2f}" if len(eps_rows) > 0 else "--",
        "eps_row2": f"{eps_rows[1]:.2f}" if len(eps_rows) > 1 else "--",
        "eps_row3": f"{eps_rows[2]:.2f}" if len(eps_rows) > 2 else "--",
        "eps_row4": f"{eps_rows[3]:.2f}" if len(eps_rows) > 3 else "--",
        "eps_row5": f"{eps_rows[4]:.2f}" if len(eps_rows) > 4 else "--",
        "current_eps": f"{evidence.eps_ttm:.2f}" if evidence.eps_ttm else "--",
        "current_pe": f"{evidence.pe_ratio:.1f}" if evidence.pe_ratio else "--",
        # Short/Medium/Long targets
        "short_term_price": short_term.price if short_term else 0,
        "short_term_rationale": short_term.rationale if short_term else "--",
        "medium_term_price": medium_term.price if medium_term else 0,
        "medium_term_rationale": medium_term.rationale if medium_term else "--",
        "long_term_price": long_term.price if long_term else 0,
        "long_term_rationale": long_term.rationale if long_term else "--",
        # Management signals
        "latest_earnings_call": evidence.management_signals.get("quarter", "--") if evidence.management_signals else "--",
        "mgmt_tone": evidence.management_signals.get("outlook_tone", "--") if evidence.management_signals else "--",
        "mgmt_key_topics": ", ".join(evidence.management_signals.get("key_topics", [])[:5]) if evidence.management_signals else "--",
        "guidance_change": evidence.management_signals.get("guidance_mentioned", "--") if evidence.management_signals else "--",
        "mgmt_risks": ", ".join(evidence.management_signals.get("risks_mentioned", [])[:3]) if evidence.management_signals else "--",
        # Catalysts and risks
        "catalysts": evidence.catalysts,
        "risks": evidence.risks,
        "change_triggers": evidence.change_triggers,
    }

    # Add sensitivity matrix cells
    for i in range(5):
        for j in range(5):
            key = f"sens_{i+1}_{j+1}"
            if i < len(sens_matrix) and j < len(sens_matrix[i]):
                context[key] = f"{sens_matrix[i][j]:.0f}"
            else:
                context[key] = "--"

    try:
        return template.render(**context)
    except Exception as e:
        logger.warning(f"Failed to render article2_v2 template: {e}, falling back to v1")
        return render_article2(evidence)


def render_article2(evidence: Article2Evidence) -> str:
    """Render Article 2 from Evidence Pack.

    Currently uses template-based rendering.
    Future: LLM enhancement for analysis sections.
    """
    date_display = evidence.date.strftime("%Y/%m/%d")

    # Build markdown (不含 H1 標題，Ghost 會自動顯示標題)
    lines = [
        f"> {date_display} | 美股蓋倫哥 | {evidence.ticker}",
        "",
        "---",
        "",
        "## 公司概覽",
        "",
        evidence.description,  # Already truncated at sentence boundary in build_article2
        "",
        "**關鍵數據**",
        f"- 市值：{evidence.market_cap}",
        f"- 產業：{evidence.sector} / {evidence.industry}",
        f"- 上市交易所：{evidence.exchange}",
        "",
        "---",
        "",
        "## 基本面分析",
        "",
    ]

    # Only show key metrics section if we have data
    if evidence.key_metrics:
        lines.extend([
            "### 關鍵 KPI",
            "",
            "| 指標 | 數值 |",
            "|------|------|",
        ])
        for metric in evidence.key_metrics:
            lines.append(
                f"| {metric.name} | {metric.current} |"
            )
    else:
        lines.append("*關鍵 KPI 資料暫無。*")

    lines.extend([
        "",
        "---",
        "",
        "## 財務面分析",
        "",
        "| 指標 | 最新季 | 去年同期 | YoY |",
        "|------|--------|----------|-----|",
    ])

    for item in evidence.financials:
        lines.append(
            f"| {item.name} | {item.current} | {item.previous or '--'} | {item.yoy_change or '--'} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 動能分析",
        "",
    ])

    # Add data timestamp
    if evidence.price_data_as_of:
        lines.append(f"*資料截至：{evidence.price_data_as_of}*")
        lines.append("")

    lines.append(f"- 現價：${evidence.current_price:,.2f}")

    # Handle weekend/market closed
    if evidence.market_closed:
        lines.append(f"- 1日變化：{evidence.price_change_1d:+.2f}%（最後交易日）")
    else:
        lines.append(f"- 1日變化：{evidence.price_change_1d:+.2f}%")

    if evidence.price_change_5d is not None:
        lines.append(f"- 5日變化：{evidence.price_change_5d:+.2f}%")

    # Add 1M and 3M returns
    if evidence.price_change_1m is not None:
        lines.append(f"- 1月報酬：{evidence.price_change_1m:+.1f}%")
    if evidence.price_change_3m is not None:
        lines.append(f"- 3月報酬：{evidence.price_change_3m:+.1f}%")

    # Add 52-week high/low
    if evidence.price_52w_high and evidence.price_52w_low:
        pct_from_high = ((evidence.current_price / evidence.price_52w_high) - 1) * 100
        pct_from_low = ((evidence.current_price / evidence.price_52w_low) - 1) * 100
        lines.append(f"- 52週高點：${evidence.price_52w_high:.2f}（距高點 {pct_from_high:+.1f}%）")
        lines.append(f"- 52週低點：${evidence.price_52w_low:.2f}（距低點 {pct_from_low:+.1f}%）")

    # Add Beta if available
    if evidence.beta:
        lines.append(f"- Beta：{evidence.beta:.2f}")

    # Only show competitor section if we have data
    if evidence.competitors:
        lines.extend([
            "",
            "---",
            "",
            "## 競爭分析",
            "",
            "### 同業比較",
            "",
            "| 公司 | 市值 | P/E | 營收成長 |",
            "|------|------|-----|----------|",
        ])

        for comp in evidence.competitors:
            pe = f"{comp.pe_ratio:.1f}" if comp.pe_ratio else "--"
            lines.append(
                f"| {comp.name} ({comp.ticker}) | {comp.market_cap} | {pe} | {comp.revenue_growth or '--'} |"
            )

    lines.extend([
        "",
        "---",
        "",
        "## 估值分析",
        "",
        "### 當前估值",
        "",
        "| 指標 | 當前值 |",
        "|------|--------|",
    ])

    # P/E display logic with proper handling of edge cases
    if evidence.pe_ratio:
        if evidence.pe_ratio > 200:
            lines.append(f"| P/E (TTM) | >200x（EPS 過低，參考性有限） |")
        elif evidence.pe_ratio < 0:
            lines.append("| P/E (TTM) | N/A（虧損期間） |")
        else:
            lines.append(f"| P/E (TTM) | {evidence.pe_ratio:.1f} |")
    elif evidence.eps_ttm is not None:
        if evidence.eps_ttm > 0.5:
            # EPS meaningful, P/E should have been calculated - show as available
            calculated_pe = evidence.current_price / evidence.eps_ttm if evidence.current_price > 0 else None
            if calculated_pe and calculated_pe > 0 and calculated_pe < 200:
                lines.append(f"| P/E (TTM) | {calculated_pe:.1f} |")
            elif calculated_pe and calculated_pe > 200:
                lines.append(f"| P/E (TTM) | >200x（EPS 過低，參考性有限） |")
            else:
                lines.append("| P/E (TTM) | N/A |")
        elif evidence.eps_ttm > 0:
            # EPS positive but too small for meaningful P/E
            lines.append(f"| P/E (TTM) | N/A（EPS ${evidence.eps_ttm:.2f} 過低） |")
        elif evidence.eps_ttm == 0:
            lines.append("| P/E (TTM) | N/A（EPS 為零） |")
        else:
            # EPS negative = loss period
            lines.append("| P/E (TTM) | N/A（虧損期間） |")
    else:
        lines.append("| P/E (TTM) | N/A |")
    if evidence.forward_pe:
        lines.append(f"| Forward P/E | {evidence.forward_pe:.1f} |")
    if evidence.ps_ratio:
        lines.append(f"| P/S | {evidence.ps_ratio:.1f} |")
    if evidence.pb_ratio:
        lines.append(f"| P/B | {evidence.pb_ratio:.1f} |")
    if evidence.ev_ebitda:
        lines.append(f"| EV/EBITDA | {evidence.ev_ebitda:.1f} |")
    # Note: EPS, ROE, FCF Yield are already shown in KPI section, skip here to avoid duplication
    if evidence.div_yield and evidence.div_yield > 0:
        lines.append(f"| 殖利率 | {evidence.div_yield * 100:.2f}% |")
    if evidence.ev and evidence.fcf_ttm and evidence.fcf_ttm > 0:
        ev_fcf = evidence.ev / evidence.fcf_ttm
        lines.append(f"| EV/FCF | {ev_fcf:.1f} |")

    lines.extend([
        "",
        "### 合理價推估",
        "",
    ])

    # Note: valuation chart removed (duplicate with table below)

    # Always show valuation cases table (required by QA gate)
    if evidence.valuation_cases:
        lines.extend([
            "| 情境 | 假設 | 目標價 | 潛在空間 |",
            "|------|------|--------|----------|",
        ])
        for case in evidence.valuation_cases:
            emoji = {"bear": "🐻", "base": "⚖️", "bull": "🐂"}.get(case.scenario, "")
            lines.append(
                f"| {emoji} {case.scenario.title()} | {case.assumption} | ${case.target_price:,.0f} | {case.upside_pct:+.1f}% |"
            )

    # Management Signals section (v5)
    if evidence.management_signals:
        ms = evidence.management_signals
        lines.extend([
            "",
            "---",
            "",
            "## 管理層訊號",
            "",
        ])
        if ms.get("quarter"):
            lines.append(f"**最近財報電話會議**：{ms['quarter']}")
        if ms.get("outlook_tone"):
            tone_display = {"bullish": "樂觀", "neutral": "中性", "cautious": "保守"}.get(
                ms["outlook_tone"], ms["outlook_tone"]
            )
            lines.append(f"- 管理層語氣：{tone_display}")
        if ms.get("key_topics"):
            lines.append(f"- 主要話題：{', '.join(ms['key_topics'][:5])}")
        if ms.get("risks_mentioned"):
            lines.append(f"- 提及風險：{', '.join(ms['risks_mentioned'][:3])}")
        if ms.get("guidance_mentioned"):
            lines.append("- 有提及前瞻指引")
        lines.append("")

    lines.extend([
        "",
        "---",
        "",
        "## 催化劑與風險",
        "",
        "### 潛在催化劑",
    ])
    for catalyst in evidence.catalysts:
        lines.append(f"- {catalyst}")

    lines.extend([
        "",
        "### 主要風險",
    ])
    for risk in evidence.risks:
        lines.append(f"- {risk}")

    lines.extend([
        "",
        "---",
        "",
        "## 風險提示",
        "",
        "本文內容僅供參考，不構成任何投資建議。投資有風險，入市需謹慎。過去績效不代表未來表現。作者可能持有或交易本文提及之股票。",
        "",
        "---",
        "",
        "*Rocket Screener — 獻給散戶的機構級分析*",
    ])

    return "\n".join(lines)


def render_article3_v2(evidence: Article3Evidence) -> str:
    """Render Article 3 v2 from Evidence Pack using Jinja2 template.

    V2 includes: Investment thesis, profit pools, benefit sequence,
    extended stock metrics, trigger conditions, and investment strategy breakdown.
    """
    env = get_template_env()
    try:
        template = env.get_template("article3_v2.md")
    except Exception as e:
        logger.warning(f"Failed to load article3_v2.md template: {e}, falling back to v1")
        return render_article3(evidence)

    date_display = evidence.date.strftime("%Y/%m/%d")

    # Prepare template context
    context = {
        "date_display": date_display,
        "theme_display": evidence.theme_display,
        "investment_thesis": evidence.investment_thesis or f"{evidence.theme_display} 產業趨勢值得關注。",
        "why_now": evidence.why_now,
        "drivers": evidence.drivers,
        "supply_chain_overview": evidence.supply_chain_overview,
        "supply_chain": evidence.supply_chain,
        "supply_chain_chart_url": evidence.supply_chain_chart_url,
        "profit_pools": evidence.profit_pools,
        "profit_pool_insight": evidence.profit_pool_insight or "詳見個別公司毛利結構。",
        "benefit_pathway": evidence.benefit_pathway or "需求驅動 → 產業鏈傳導 → 相關公司受惠",
        "benefit_sequence": evidence.benefit_sequence,
        "market_cap_timestamp": evidence.market_cap_as_of,
        "representative_stocks": evidence.representative_stocks,
        "kpi1_name": evidence.kpi1_name or "KPI 1",
        "kpi2_name": evidence.kpi2_name or "KPI 2",
        "kpi3_name": evidence.kpi3_name or "KPI 3",
        "bull_case": evidence.bull_case,
        "bull_triggers": evidence.bull_triggers,
        "bull_beneficiaries": evidence.bull_beneficiaries or "產業龍頭",
        "base_case": evidence.base_case,
        "base_assumptions": evidence.base_assumptions,
        "bear_case": evidence.bear_case,
        "bear_triggers": evidence.bear_triggers,
        "bear_losers": evidence.bear_losers or "競爭力較弱者",
        "investment_strategy": evidence.investment_strategy,
        "conservative_picks": evidence.conservative_picks,
        "conservative_rationale": evidence.conservative_rationale or "",
        "growth_picks": evidence.growth_picks,
        "growth_rationale": evidence.growth_rationale or "",
        "aggressive_picks": evidence.aggressive_picks,
        "aggressive_rationale": evidence.aggressive_rationale or "",
        "industry_kpis": evidence.industry_kpis,
        "upcoming_events": evidence.upcoming_events,
        "upgrade_conditions": evidence.upgrade_conditions,
        "downgrade_conditions": evidence.downgrade_conditions,
    }

    try:
        return template.render(**context)
    except Exception as e:
        logger.warning(f"Failed to render article3_v2 template: {e}, falling back to v1")
        return render_article3(evidence)


def render_article3(evidence: Article3Evidence) -> str:
    """Render Article 3 from Evidence Pack."""
    date_display = evidence.date.strftime("%Y/%m/%d")

    # Build markdown (不含 H1 標題，Ghost 會自動顯示標題)
    lines = [
        f"> {date_display} | 美股蓋倫哥 | {evidence.theme}",
        "",
        "---",
        "",
        "## 為何現在關注？",
        "",
        evidence.why_now,
        "",
        "---",
        "",
        "## 驅動因子",
        "",
    ]

    for i, driver in enumerate(evidence.drivers, 1):
        lines.extend([
            f"### {i}. {driver.title}",
            "",
            driver.description,
            "",
        ])

    lines.extend([
        "---",
        "",
        "## 產業鏈 / 供應鏈框架",
        "",
        evidence.supply_chain_overview,
        "",
    ])

    if evidence.supply_chain_chart_url:
        lines.append(f"![產業鏈圖]({evidence.supply_chain_chart_url})")
    else:
        lines.extend([
            "### 產業鏈結構",
            "",
            "| 位置 | 環節 | 代表公司 | 說明 |",
            "|------|------|----------|------|",
        ])
        for layer in evidence.supply_chain:
            lines.append(
                f"| {layer.position} | {layer.segment} | {layer.companies} | {layer.notes} |"
            )

    lines.extend([
        "",
        "---",
        "",
        "## 代表股票",
        "",
    ])

    # Add market cap timestamp if available
    if evidence.market_cap_as_of:
        lines.append(f"*市值資料截至：{evidence.market_cap_as_of}*")
        lines.append("")

    lines.extend([
        "| 股票 | 市值 | 核心業務 | 產業鏈位置 | 觀點 |",
        "|------|------|----------|------------|------|",
    ])

    for stock in evidence.representative_stocks:
        lines.append(
            f"| {stock.ticker} | {stock.market_cap} | {stock.business} | {stock.position} | {stock.view} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 情境展望",
        "",
        "### 🐂 Bull Case（樂觀情境）",
        evidence.bull_case,
        "",
        "### ⚖️ Base Case（基準情境）",
        evidence.base_case,
        "",
        "### 🐻 Bear Case（悲觀情境）",
        evidence.bear_case,
        "",
        "---",
        "",
        "## 投資策略建議",
        "",
        evidence.investment_strategy,
        "",
        "---",
        "",
        "## 關注時點",
        "",
    ])

    for event in evidence.upcoming_events:
        event_date = event.get('date', '')
        event_desc = event.get('description', '')
        if event_date and event_desc:
            lines.append(f"- **{event_date}**：{event_desc}")
        elif event_desc:
            lines.append(f"- {event_desc}")
    # If no events, add a placeholder message
    if not evidence.upcoming_events:
        lines.append("- 請關注公司官網及財報發布時程")

    lines.extend([
        "",
        "---",
        "",
        "## 風險提示",
        "",
        "本文內容僅供參考，不構成任何投資建議。投資有風險，入市需謹慎。過去績效不代表未來表現。",
        "",
        "---",
        "",
        "*Rocket Screener — 獻給散戶的機構級分析*",
    ])

    return "\n".join(lines)
