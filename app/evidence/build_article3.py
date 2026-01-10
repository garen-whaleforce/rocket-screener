"""Build Evidence Pack for Article 3 (Theme/Sector)."""

import logging
from datetime import date
from pathlib import Path
from typing import Optional

from app.evidence.schemas import (
    Article3Evidence,
    RepresentativeStock,
    SupplyChainLayer,
    ThemeDriver,
)
from app.features.theme_detection import DetectedTheme
from app.ingest.fmp_client import FMPClient

logger = logging.getLogger(__name__)

# Pre-defined theme content (will be enhanced with LLM in future versions)
THEME_CONTENT = {
    "ai-server": {
        "why_now": "AI 大模型訓練與推論需求爆發，帶動 GPU、HBM、先進封裝等關鍵環節供不應求，資料中心資本支出持續攀升。",
        "drivers": [
            ThemeDriver(
                title="算力需求指數級成長",
                description="大型語言模型參數量從數十億成長至數兆，訓練與推論所需算力每年翻倍成長，推動 GPU 與 AI 加速器需求。",
            ),
            ThemeDriver(
                title="雲端巨頭 Capex 競賽",
                description="微軟、Meta、Google、Amazon 等持續加碼資料中心投資，預計 2025 年 AI 相關資本支出將創歷史新高。",
            ),
            ThemeDriver(
                title="先進封裝成為新瓶頸",
                description="CoWoS、HBM 等先進封裝技術供給吃緊，成為限制 AI 晶片出貨的關鍵瓶頸，相關供應商議價能力提升。",
            ),
        ],
        "supply_chain_overview": "AI 伺服器供應鏈從上游晶片設計、中游封裝製造，到下游系統整合，形成完整生態系。",
        "supply_chain": [
            SupplyChainLayer(position="上游", segment="GPU/ASIC 設計", companies="NVDA, AMD, GOOG (TPU)", notes="核心運算晶片，高毛利"),
            SupplyChainLayer(position="上游", segment="HBM 記憶體", companies="SK Hynix, Samsung, MU", notes="高頻寬記憶體，供給吃緊"),
            SupplyChainLayer(position="中游", segment="晶圓代工", companies="TSM", notes="先進製程獨佔，產能搶手"),
            SupplyChainLayer(position="中游", segment="先進封裝", companies="TSM (CoWoS), ASE", notes="關鍵瓶頸環節"),
            SupplyChainLayer(position="下游", segment="伺服器組裝", companies="SMCI, Dell, HPE", notes="系統整合，毛利較低"),
        ],
        "stocks": [
            ("NVDA", "GPU 設計龍頭", "上游", "AI 浪潮最大受益者"),
            ("AMD", "GPU/CPU 設計", "上游", "市占持續提升"),
            ("TSM", "晶圓代工", "中游", "先進製程壟斷"),
            ("MU", "記憶體", "中游", "HBM 產能擴張"),
            ("SMCI", "伺服器組裝", "下游", "AI 伺服器專家"),
        ],
        "bull_case": "AI 需求超預期成長，供應鏈全線受惠，產能持續吃緊帶動 ASP 上漲，相關股票估值持續擴張。",
        "base_case": "AI 投資維持高成長但符合市場預期，供應鏈穩健成長，估值維持當前水準。",
        "bear_case": "AI 投資放緩或不如預期，庫存調整風險浮現，估值面臨收縮壓力。",
        "investment_strategy": "建議關注具備技術護城河與定價能力的上游晶片設計公司，以及供給吃緊的 HBM 與先進封裝環節。下游組裝因毛利較低，建議觀望為主。",
    },
    "ai-software": {
        "why_now": "生成式 AI 從技術驗證進入商業化落地階段，企業 AI 導入加速，軟體平台與應用層開始看到營收貢獻。",
        "drivers": [
            ThemeDriver(title="企業 AI 導入加速", description="從 Copilot 到自動化客服，企業開始將 AI 整合進核心工作流程。"),
            ThemeDriver(title="平台競爭白熱化", description="微軟、Google、Meta 持續投入大模型研發，平台生態系之爭決定長期勝負。"),
            ThemeDriver(title="應用層商業模式成形", description="訂閱制、API 調用計費等商業模式日趨成熟。"),
        ],
        "supply_chain_overview": "AI 軟體生態從基礎模型、開發平台到終端應用，形成多層價值鏈。",
        "supply_chain": [
            SupplyChainLayer(position="基礎層", segment="大型語言模型", companies="OpenAI, Anthropic, GOOGL", notes="核心技術提供者"),
            SupplyChainLayer(position="平台層", segment="雲端 AI 服務", companies="MSFT (Azure), AMZN (AWS), GOOGL (GCP)", notes="企業部署首選"),
            SupplyChainLayer(position="應用層", segment="企業軟體", companies="CRM, ADBE, NOW", notes="AI 功能整合"),
        ],
        "stocks": [
            ("MSFT", "雲端 + Copilot", "平台層", "AI 整合最完整"),
            ("GOOGL", "搜尋 + 雲端 + Gemini", "全棧", "技術領先者"),
            ("CRM", "企業 CRM + AI", "應用層", "Einstein AI"),
        ],
        "bull_case": "AI 商業化超預期，企業訂閱大幅成長，平台公司獲利能力提升。",
        "base_case": "商業化穩步推進，符合市場預期成長軌跡。",
        "bear_case": "商業化進度不如預期，企業 IT 支出縮減。",
        "investment_strategy": "優先關注具備平台優勢與既有客戶基礎的龍頭公司，應用層選擇已有 AI 產品且能帶動訂閱成長者。",
    },
}


def build_article3_evidence(
    target_date: date,
    fmp_client: Optional[FMPClient],
    theme: DetectedTheme,
    recent_news: Optional[list[str]] = None,
) -> Article3Evidence:
    """Build complete Article 3 Evidence Pack.

    Args:
        target_date: Date for the article
        fmp_client: FMP client
        theme: Selected theme
        recent_news: Recent news headlines related to the theme

    Returns:
        Article3Evidence ready for rendering
    """
    from app.llm.client import get_llm_client

    theme_id = theme.theme_id
    content = THEME_CONTENT.get(theme_id, THEME_CONTENT["ai-server"])

    # Get stock data for representative stocks
    representative_stocks = []
    stock_data = content.get("stocks", [])

    for ticker, business, position, view in stock_data:
        market_cap = "--"
        if fmp_client:
            try:
                profile = fmp_client.get_company_profile(ticker)
                if profile:
                    cap = profile.get("mktCap", 0)
                    if cap >= 1_000_000_000_000:
                        market_cap = f"${cap / 1_000_000_000_000:.2f}T"
                    elif cap >= 1_000_000_000:
                        market_cap = f"${cap / 1_000_000_000:.0f}B"
            except Exception:
                pass

        representative_stocks.append(
            RepresentativeStock(
                ticker=ticker,
                name=ticker,  # Could fetch from profile
                market_cap=market_cap,
                business=business,
                position=position,
                view=view,
            )
        )

    # Use LLM to enhance theme analysis if available
    why_now = content["why_now"]
    drivers = content["drivers"]
    bull_case = content["bull_case"]
    bear_case = content["bear_case"]
    investment_strategy = content["investment_strategy"]

    llm_client = get_llm_client()
    if llm_client and recent_news:
        try:
            stocks_for_llm = [
                {"ticker": s.ticker, "business": s.business}
                for s in representative_stocks
            ]
            analysis = llm_client.generate_theme_analysis(
                theme=theme_id,
                theme_display=theme.display_name,
                representative_stocks=stocks_for_llm,
                recent_news=recent_news or [],
            )
            why_now = analysis.get("why_now", why_now)
            if analysis.get("drivers"):
                drivers = [
                    ThemeDriver(title=d["title"], description=d["description"])
                    for d in analysis["drivers"]
                ]
            bull_case = analysis.get("bull_case", bull_case)
            bear_case = analysis.get("bear_case", bear_case)
            investment_strategy = analysis.get("investment_strategy", investment_strategy)
            logger.info(f"LLM enhanced theme analysis for {theme_id}")
        except Exception as e:
            logger.warning(f"LLM theme analysis failed: {e}")

    return Article3Evidence(
        date=target_date,
        theme=theme_id,
        theme_display=theme.display_name,
        why_now=why_now,
        drivers=drivers,
        supply_chain_overview=content["supply_chain_overview"],
        supply_chain=content["supply_chain"],
        representative_stocks=representative_stocks,
        bull_case=bull_case,
        base_case=content["base_case"],
        bear_case=bear_case,
        investment_strategy=investment_strategy,
        upcoming_events=[
            {"date": "持續關注", "description": "大型科技股財報"},
            {"date": "每季", "description": "資料中心 Capex 更新"},
        ],
    )


def generate_supply_chain_chart_for_article3(
    evidence: Article3Evidence,
    output_dir: Path,
) -> Optional[str]:
    """Generate supply chain chart for Article 3.

    Args:
        evidence: Article3Evidence with supply chain data
        output_dir: Directory to save chart

    Returns:
        Path to generated PNG, or None if failed
    """
    try:
        from app.features.supply_chain_chart import generate_supply_chain_chart_from_evidence

        chart_path = generate_supply_chain_chart_from_evidence(evidence, output_dir)
        if chart_path:
            evidence.supply_chain_chart_url = chart_path
            logger.info(f"Generated supply chain chart: {chart_path}")
        return chart_path
    except Exception as e:
        logger.warning(f"Failed to generate supply chain chart: {e}")
        return None
