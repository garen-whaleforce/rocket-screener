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

    # Build markdown
    lines = [
        f"# 美股盤後晨報 | {date_display}",
        "",
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


def render_article2(evidence: Article2Evidence) -> str:
    """Render Article 2 from Evidence Pack.

    Currently uses template-based rendering.
    Future: LLM enhancement for analysis sections.
    """
    date_display = evidence.date.strftime("%Y/%m/%d")

    lines = [
        f"# 個股深度｜{evidence.ticker} {evidence.company_name}",
        "",
        f"> {date_display} | 美股蓋倫哥 | {evidence.ticker}",
        "",
        "---",
        "",
        "## 公司概覽",
        "",
        evidence.description[:500] + "..." if len(evidence.description) > 500 else evidence.description,
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
        "詳細基本面分析請參考以下關鍵指標。",
        "",
        "### 關鍵 KPI",
        "",
        "| 指標 | 數值 | YoY 變化 |",
        "|------|------|----------|",
    ]

    for metric in evidence.key_metrics:
        lines.append(
            f"| {metric.name} | {metric.current} | {metric.yoy_change or '--'} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 財務面分析",
        "",
        "| 指標 | 最新季 | 前一季 | YoY |",
        "|------|--------|--------|-----|",
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
        f"- 現價：${evidence.current_price:,.2f}",
        f"- 1日變化：{evidence.price_change_1d:+.2f}%",
    ])

    if evidence.price_change_5d is not None:
        lines.append(f"- 5日變化：{evidence.price_change_5d:+.2f}%")

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

    if evidence.pe_ratio:
        lines.append(f"| P/E (TTM) | {evidence.pe_ratio:.1f} |")
    if evidence.forward_pe:
        lines.append(f"| Forward P/E | {evidence.forward_pe:.1f} |")
    if evidence.ps_ratio:
        lines.append(f"| P/S | {evidence.ps_ratio:.1f} |")
    if evidence.ev_ebitda:
        lines.append(f"| EV/EBITDA | {evidence.ev_ebitda:.1f} |")

    lines.extend([
        "",
        "### 合理價推估",
        "",
    ])

    if evidence.valuation_chart_url:
        lines.append(f"![估值模型]({evidence.valuation_chart_url})")
    else:
        lines.extend([
            "| 情境 | 假設 | 目標價 | 潛在空間 |",
            "|------|------|--------|----------|",
        ])
        for case in evidence.valuation_cases:
            emoji = {"bear": "🐻", "base": "⚖️", "bull": "🐂"}.get(case.scenario, "")
            lines.append(
                f"| {emoji} {case.scenario.title()} | {case.assumption} | ${case.target_price:,.0f} | {case.upside_pct:+.1f}% |"
            )

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


def render_article3(evidence: Article3Evidence) -> str:
    """Render Article 3 from Evidence Pack."""
    date_display = evidence.date.strftime("%Y/%m/%d")

    lines = [
        f"# 產業趨勢｜{evidence.theme_display}",
        "",
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
        lines.append(f"- **{event.get('date', 'TBD')}**：{event.get('description', '')}")

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
