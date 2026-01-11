"""Build Evidence Pack for Article 3 (Theme/Sector).

v2 additions:
- Investment thesis
- Profit pool analysis
- Benefit sequence (who benefits first)
- Extended stock metrics (returns, valuations, KPIs)
- Bull/Bear trigger conditions
- Investment strategy breakdown
- Industry KPIs for monitoring
"""

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from app.evidence.schemas import (
    Article3Evidence,
    BenefitStep,
    IndustryKPI,
    ProfitPool,
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
    "semiconductor": {
        "why_now": "半導體產業週期回升，AI 與先進製程需求強勁，地緣政治推動各國建立本土供應鏈。",
        "drivers": [
            ThemeDriver(title="AI 驅動先進製程需求", description="AI 晶片需要最先進的製程技術，3nm/2nm 產能成為兵家必爭之地。"),
            ThemeDriver(title="庫存週期觸底回升", description="消費性電子與車用晶片庫存調整結束，新一輪備貨需求啟動。"),
            ThemeDriver(title="地緣政治推動投資", description="美國 CHIPS 法案、歐洲晶片法案等推動本土製造投資。"),
        ],
        "supply_chain_overview": "半導體供應鏈從設計、設備、材料到製造，形成高度分工的全球生態系。",
        "supply_chain": [
            SupplyChainLayer(position="上游", segment="IC 設計", companies="NVDA, AMD, QCOM, AVGO", notes="IP 與設計核心"),
            SupplyChainLayer(position="上游", segment="EDA 工具", companies="SNPS, CDNS", notes="設計必備軟體"),
            SupplyChainLayer(position="中游", segment="設備製造", companies="ASML, AMAT, LRCX, KLAC", notes="關鍵製造設備"),
            SupplyChainLayer(position="中游", segment="晶圓代工", companies="TSM, INTC, Samsung", notes="製造核心環節"),
            SupplyChainLayer(position="下游", segment="封裝測試", companies="ASE, Amkor", notes="後段製程"),
        ],
        "stocks": [
            ("TSM", "晶圓代工龍頭", "中游", "先進製程獨佔優勢"),
            ("ASML", "EUV 設備獨佔", "中游", "關鍵設備供應商"),
            ("AMAT", "半導體設備", "中游", "製程設備龍頭"),
            ("NVDA", "AI 晶片設計", "上游", "AI 浪潮領導者"),
            ("INTC", "IDM 巨頭", "中游", "美國製造復興"),
        ],
        "bull_case": "AI 需求持續超預期，先進製程供不應求，設備訂單創新高。",
        "base_case": "產業週期回升，AI 帶動結構性成長，符合市場預期。",
        "bear_case": "終端需求不如預期，產能過剩風險浮現，價格競爭加劇。",
        "investment_strategy": "優先布局先進製程相關設備商與晶圓代工龍頭，關注地緣政治受惠的美國本土製造投資機會。",
    },
    "ev": {
        "why_now": "電動車滲透率持續攀升，電池技術突破與充電基礎設施擴建加速產業發展。",
        "drivers": [
            ThemeDriver(title="滲透率加速成長", description="全球電動車銷量持續創新高，主要市場滲透率突破臨界點後加速成長。"),
            ThemeDriver(title="電池技術突破", description="固態電池、快充技術等突破，解決里程焦慮與充電時間問題。"),
            ThemeDriver(title="充電基礎設施擴建", description="各國政府補貼推動充電站建設，消除里程焦慮障礙。"),
        ],
        "supply_chain_overview": "電動車供應鏈從電池材料、電池芯到整車製造，形成完整生態系。",
        "supply_chain": [
            SupplyChainLayer(position="上游", segment="電池材料", companies="ALB, SQM, LTHM", notes="鋰、鈷、鎳等關鍵材料"),
            SupplyChainLayer(position="中游", segment="電池製造", companies="CATL, Panasonic, LG Energy", notes="電池芯製造"),
            SupplyChainLayer(position="中游", segment="電池管理系統", companies="TI, NXP", notes="BMS 與電子控制"),
            SupplyChainLayer(position="下游", segment="整車製造", companies="TSLA, BYD, RIVN, LCID", notes="電動車品牌"),
            SupplyChainLayer(position="基建", segment="充電設施", companies="CHPT, BLNK, EVgo", notes="充電網絡營運"),
        ],
        "stocks": [
            ("TSLA", "電動車龍頭", "下游", "技術與品牌領導者"),
            ("RIVN", "電動皮卡", "下游", "商用車市場潛力"),
            ("CHPT", "充電網絡", "基建", "充電基礎設施龍頭"),
            ("ALB", "鋰礦龍頭", "上游", "電池材料受惠"),
            ("LCID", "豪華電動車", "下游", "技術領先者"),
        ],
        "bull_case": "電動車滲透率加速突破，電池成本下降推動平價車型，基建投資帶動充電股。",
        "base_case": "產業穩健成長，滲透率按預期提升，競爭格局逐步底定。",
        "bear_case": "價格戰壓縮毛利，補貼退場影響需求，充電基建投資回報不如預期。",
        "investment_strategy": "關注具備技術與規模優勢的整車廠，以及受惠於基建投資的充電設施營運商。上游材料股波動較大，建議謹慎。",
    },
    "cloud": {
        "why_now": "企業數位轉型持續，雲端支出重啟成長，AI 服務成為新的成長引擎。",
        "drivers": [
            ThemeDriver(title="企業雲端支出回升", description="經歷優化期後，企業 IT 支出重啟成長，雲端遷移進入新階段。"),
            ThemeDriver(title="AI 服務帶動成長", description="雲端平台整合 AI 能力，成為企業導入 AI 的首選途徑。"),
            ThemeDriver(title="混合雲策略普及", description="企業採用混合雲架構，帶動公有雲與私有雲解決方案需求。"),
        ],
        "supply_chain_overview": "雲端運算生態從基礎設施、平台服務到應用軟體，形成多層價值鏈。",
        "supply_chain": [
            SupplyChainLayer(position="基礎層", segment="IaaS 服務", companies="AMZN (AWS), MSFT (Azure), GOOGL (GCP)", notes="基礎運算資源"),
            SupplyChainLayer(position="平台層", segment="PaaS 服務", companies="SNOW, DDOG, MDB", notes="資料與開發平台"),
            SupplyChainLayer(position="應用層", segment="SaaS 服務", companies="CRM, NOW, WDAY", notes="企業應用軟體"),
            SupplyChainLayer(position="安全層", segment="雲端安全", companies="CRWD, ZS, PANW", notes="安全解決方案"),
        ],
        "stocks": [
            ("AMZN", "AWS 雲端龍頭", "基礎層", "市佔率領先者"),
            ("MSFT", "Azure 雲端", "基礎層", "成長最快"),
            ("SNOW", "資料雲平台", "平台層", "資料倉儲領導者"),
            ("CRM", "SaaS 龍頭", "應用層", "企業 CRM 第一"),
            ("CRWD", "雲端安全", "安全層", "端點安全領導者"),
        ],
        "bull_case": "企業雲端支出加速成長，AI 服務帶動 ARPU 提升，雲端股估值重估。",
        "base_case": "雲端支出穩健成長，AI 整合帶來漸進式貢獻。",
        "bear_case": "企業 IT 支出縮減，雲端優化週期延長，競爭壓力加劇。",
        "investment_strategy": "優先關注具備 AI 整合能力的雲端平台龍頭，以及在特定領域具備護城河的 SaaS 公司。",
    },
    "biotech": {
        "why_now": "GLP-1 減重藥物熱潮帶動生技股重獲關注，FDA 審批節奏加快，併購活動升溫。",
        "drivers": [
            ThemeDriver(title="GLP-1 藥物革命", description="減重藥物市場爆發，相關藥廠營收與股價創新高，帶動整體生技板塊關注度。"),
            ThemeDriver(title="FDA 審批加速", description="監管機構加速審批流程，新藥上市時程縮短。"),
            ThemeDriver(title="併購活動升溫", description="大型藥廠現金充沛，積極併購具潛力的生技公司填補產品線。"),
        ],
        "supply_chain_overview": "生技製藥產業從藥物發現、臨床試驗到商業化，形成高度專業分工的價值鏈。",
        "supply_chain": [
            SupplyChainLayer(position="上游", segment="藥物發現", companies="學術機構, 新創公司", notes="早期研發"),
            SupplyChainLayer(position="中游", segment="臨床開發", companies="生技公司, CRO 服務商", notes="臨床試驗執行"),
            SupplyChainLayer(position="下游", segment="商業化", companies="LLY, NVO, AMGN, BIIB", notes="藥品銷售"),
            SupplyChainLayer(position="服務", segment="CDMO", companies="WuXi, Lonza, Thermo Fisher", notes="委託生產"),
        ],
        "stocks": [
            ("LLY", "GLP-1 龍頭", "下游", "減重藥物領導者"),
            ("NVO", "Ozempic 製造商", "下游", "糖尿病與減重藥物"),
            ("AMGN", "大型生技", "下游", "多元產品線"),
            ("MRNA", "mRNA 技術", "中游", "技術平台領先"),
            ("GILD", "抗病毒專家", "下游", "穩定現金流"),
        ],
        "bull_case": "GLP-1 市場超預期擴大，新適應症獲批，併購溢價持續。",
        "base_case": "GLP-1 維持強勁成長，產業穩健發展。",
        "bear_case": "競爭加劇壓縮毛利，臨床試驗失敗，監管風險。",
        "investment_strategy": "關注 GLP-1 領域龍頭以及具備併購價值的中型生技股。風險承受度較低者可考慮多元化的大型製藥公司。",
    },
    "fintech": {
        "why_now": "支付數位化加速，加密貨幣監管明朗化，嵌入式金融創造新成長機會。",
        "drivers": [
            ThemeDriver(title="支付數位化加速", description="現金使用持續下降，電子支付與行動支付滲透率創新高。"),
            ThemeDriver(title="加密貨幣監管明朗", description="主要國家監管框架逐步建立，機構投資者參與度提升。"),
            ThemeDriver(title="嵌入式金融興起", description="金融服務整合進非金融平台，創造新的分發渠道。"),
        ],
        "supply_chain_overview": "金融科技生態從支付處理、數位銀行到加密資產，形成多元的服務層次。",
        "supply_chain": [
            SupplyChainLayer(position="基礎層", segment="支付網絡", companies="V, MA", notes="全球支付基礎設施"),
            SupplyChainLayer(position="平台層", segment="支付處理", companies="PYPL, SQ, ADYEN", notes="商家支付解決方案"),
            SupplyChainLayer(position="應用層", segment="數位銀行", companies="SoFi, Revolut, Chime", notes="新型銀行服務"),
            SupplyChainLayer(position="加密", segment="加密交易", companies="COIN, 幣安", notes="加密貨幣交易所"),
        ],
        "stocks": [
            ("V", "支付網絡龍頭", "基礎層", "全球支付領導者"),
            ("MA", "支付網絡", "基礎層", "高成長市場布局"),
            ("PYPL", "數位支付", "平台層", "用戶規模領先"),
            ("SQ", "商家服務", "平台層", "中小企業支付"),
            ("COIN", "加密交易所", "加密", "美國合規龍頭"),
        ],
        "bull_case": "支付數位化超預期，加密貨幣主流化，嵌入式金融帶動新成長。",
        "base_case": "支付穩健成長，加密貨幣波動中發展。",
        "bear_case": "經濟衰退衝擊消費支付，加密貨幣監管收緊，競爭壓縮手續費率。",
        "investment_strategy": "支付網絡龍頭 Visa/Mastercard 為核心持股，加密貨幣部位根據風險承受度配置。關注嵌入式金融帶來的新機會。",
    },
}

# V2 Theme Content: Profit Pools, Benefit Sequence, KPIs, Triggers
THEME_CONTENT_V2 = {
    "ai-server": {
        "investment_thesis": "AI 運算需求指數成長，GPU 與先進封裝供應吃緊，產業鏈上游掌握定價權，建議配置龍頭晶片設計與封裝環節。",
        "profit_pools": [
            ProfitPool(position="上游", margin_range="60-75%", pricing_power="強", bottleneck="高", companies="NVDA, AMD"),
            ProfitPool(position="中游", margin_range="45-55%", pricing_power="強", bottleneck="高", companies="TSM, MU"),
            ProfitPool(position="下游", margin_range="10-20%", pricing_power="弱", bottleneck="低", companies="SMCI, Dell"),
        ],
        "profit_pool_insight": "毛利集中在上游晶片設計與中游代工環節，下游伺服器組裝毛利低但受惠量成長；HBM 與 CoWoS 產能為當前最大瓶頸。",
        "benefit_pathway": "AI 模型參數成長 → GPU 需求爆發 → 晶圓代工與封裝吃緊 → 記憶體（HBM）供不應求 → 伺服器出貨放量",
        "benefit_sequence": [
            BenefitStep(segment="GPU 設計", tickers="NVDA, AMD", trigger="雲端 Capex 增加", timing="立即"),
            BenefitStep(segment="晶圓代工", tickers="TSM", trigger="先進製程訂單", timing="1-2 季"),
            BenefitStep(segment="HBM 記憶體", tickers="MU, SK Hynix", trigger="AI 晶片量產", timing="2-3 季"),
            BenefitStep(segment="伺服器組裝", tickers="SMCI, Dell", trigger="系統出貨", timing="3-4 季"),
        ],
        "kpi1_name": "HBM 供給量",
        "kpi2_name": "CoWoS 產能",
        "kpi3_name": "雲端 Capex",
        "industry_kpis": [
            IndustryKPI(name="HBM 供給量 (GB)", description="高頻寬記憶體年度出貨量", current="~30GB (2024E)"),
            IndustryKPI(name="CoWoS 月產能", description="先進封裝月產能（片）", current="~40K wafers/month"),
            IndustryKPI(name="雲端 AI Capex", description="四大雲端商年度 AI 資本支出", current="~$200B (2025E)"),
        ],
        "bull_triggers": ["雲端 Capex 上修 > 20%", "HBM 供給持續吃緊", "新 AI 應用爆發（如 Agent）"],
        "bear_triggers": ["終端 AI 需求放緩", "庫存水位上升", "政策限制（如出口管制）"],
        "base_assumptions": ["AI Capex 維持 20-30% YoY 成長", "供給逐步改善但仍吃緊", "估值維持高位"],
        "bull_beneficiaries": "NVDA, TSM, MU — 直接受惠需求超預期",
        "bear_losers": "SMCI, DELL — 毛利低、估值敏感",
        "conservative_picks": "TSM, ASML",
        "conservative_rationale": "技術護城河深，產能獨佔，長期配置首選",
        "growth_picks": "NVDA, MU",
        "growth_rationale": "AI 需求直接受惠，成長動能最強",
        "aggressive_picks": "SMCI, AMD",
        "aggressive_rationale": "高 beta，量成長可帶動股價，但毛利壓力需留意",
        "upgrade_conditions": ["雲端 Capex 連續兩季上修", "新 AI 應用普及（如 Agent 生態）"],
        "downgrade_conditions": ["HBM/GPU 庫存週轉天數上升", "主要客戶 Capex 下修"],
    },
    "semiconductor": {
        "investment_thesis": "半導體週期觸底回升，AI 與先進製程為結構性成長動能，設備與 EDA 為高確定性環節。",
        "profit_pools": [
            ProfitPool(position="上游 IC設計", margin_range="50-70%", pricing_power="強", bottleneck="中", companies="NVDA, QCOM"),
            ProfitPool(position="上游 EDA", margin_range="80-85%", pricing_power="強", bottleneck="低", companies="SNPS, CDNS"),
            ProfitPool(position="中游 設備", margin_range="40-50%", pricing_power="強", bottleneck="高", companies="ASML, AMAT"),
            ProfitPool(position="中游 代工", margin_range="50-55%", pricing_power="強", bottleneck="高", companies="TSM"),
            ProfitPool(position="下游 封測", margin_range="15-25%", pricing_power="弱", bottleneck="低", companies="ASE"),
        ],
        "profit_pool_insight": "EDA 軟體毛利最高但成長穩定；設備與代工具備定價權；封測毛利最低，競爭激烈。",
        "benefit_pathway": "終端需求回升 → IC 設計啟動新案 → 設備訂單增加 → 代工產能利用率回升 → 封測跟進",
        "benefit_sequence": [
            BenefitStep(segment="EDA 軟體", tickers="SNPS, CDNS", trigger="新晶片設計案", timing="立即"),
            BenefitStep(segment="半導體設備", tickers="ASML, AMAT", trigger="產能擴張", timing="1-2 季"),
            BenefitStep(segment="晶圓代工", tickers="TSM", trigger="訂單滿載", timing="2-3 季"),
            BenefitStep(segment="封裝測試", tickers="ASE", trigger="出貨放量", timing="3-4 季"),
        ],
        "kpi1_name": "設備訂單",
        "kpi2_name": "產能利用率",
        "kpi3_name": "庫存天數",
        "industry_kpis": [
            IndustryKPI(name="WFE 設備訂單", description="晶圓廠設備年度訂單", current="~$100B (2024E)"),
            IndustryKPI(name="先進製程利用率", description="3nm/5nm 產能利用率", current="85-90%"),
            IndustryKPI(name="通路庫存天數", description="半導體通路商庫存週轉", current="~50 天"),
        ],
        "bull_triggers": ["設備訂單連續上修", "庫存週期結束、補貨啟動", "地緣政治推動本土投資"],
        "bear_triggers": ["終端需求不如預期", "庫存調整延長", "設備訂單取消/遞延"],
        "base_assumptions": ["週期觸底回升", "AI 帶動結構性需求", "設備投資穩健"],
        "bull_beneficiaries": "ASML, TSM — 設備與代工龍頭直接受惠",
        "bear_losers": "二線設備商、成熟製程代工 — 競爭加劇",
        "conservative_picks": "TSM, ASML",
        "conservative_rationale": "技術領先、壟斷地位、長期穩健",
        "growth_picks": "AMAT, LRCX",
        "growth_rationale": "設備週期復甦受惠，訂單能見度高",
        "aggressive_picks": "INTC",
        "aggressive_rationale": "美國製造復興概念，但執行風險高",
        "upgrade_conditions": ["設備訂單加速成長", "先進製程供不應求"],
        "downgrade_conditions": ["終端需求大幅放緩", "庫存再度堆積"],
    },
    "ev": {
        "investment_thesis": "電動車滲透率進入加速期，電池成本下降與充電基建完善將推動普及，但價格戰壓縮毛利需謹慎。",
        "profit_pools": [
            ProfitPool(position="上游 材料", margin_range="20-40%", pricing_power="中", bottleneck="中", companies="ALB, SQM"),
            ProfitPool(position="中游 電池", margin_range="15-25%", pricing_power="中", bottleneck="高", companies="CATL, Panasonic"),
            ProfitPool(position="下游 整車", margin_range="10-25%", pricing_power="中", bottleneck="低", companies="TSLA, RIVN"),
            ProfitPool(position="基建 充電", margin_range="5-15%", pricing_power="弱", bottleneck="低", companies="CHPT, BLNK"),
        ],
        "profit_pool_insight": "電池為核心環節，規模經濟決定毛利；整車品牌差異化為關鍵；充電營運商尚未獲利。",
        "benefit_pathway": "政策補貼/油價上漲 → EV 需求增加 → 電池訂單成長 → 材料需求拉動 → 充電利用率提升",
        "benefit_sequence": [
            BenefitStep(segment="整車製造", tickers="TSLA, RIVN", trigger="訂單增加", timing="立即"),
            BenefitStep(segment="電池製造", tickers="CATL, Panasonic", trigger="整車拉貨", timing="1-2 季"),
            BenefitStep(segment="電池材料", tickers="ALB, SQM", trigger="電池擴產", timing="2-3 季"),
            BenefitStep(segment="充電網絡", tickers="CHPT, BLNK", trigger="車輛普及", timing="3-5 年"),
        ],
        "kpi1_name": "交車量",
        "kpi2_name": "電池成本",
        "kpi3_name": "充電利用率",
        "industry_kpis": [
            IndustryKPI(name="全球 EV 交車量", description="年度電動車銷量", current="~14M (2024E)"),
            IndustryKPI(name="電池成本 ($/kWh)", description="電池包成本", current="~$130/kWh"),
            IndustryKPI(name="充電樁利用率", description="公共充電站使用率", current="~15-20%"),
        ],
        "bull_triggers": ["滲透率加速突破", "電池成本大幅下降", "充電基建補貼加碼"],
        "bear_triggers": ["價格戰惡化毛利", "補貼退場", "二手 EV 殘值崩跌"],
        "base_assumptions": ["滲透率穩步成長至 25-30%", "價格競爭持續但可控", "基建投資穩健"],
        "bull_beneficiaries": "TSLA — 規模與品牌優勢最強",
        "bear_losers": "RIVN, LCID — 規模小、現金消耗快",
        "conservative_picks": "TSLA",
        "conservative_rationale": "規模經濟與品牌領先，執行力最佳",
        "growth_picks": "RIVN, CHPT",
        "growth_rationale": "成長空間大但風險高，適合積極型投資人",
        "aggressive_picks": "LCID, BLNK",
        "aggressive_rationale": "高波動、投機性強，需嚴格停損",
        "upgrade_conditions": ["價格戰緩和、毛利回穩", "充電利用率大幅提升"],
        "downgrade_conditions": ["主要車廠毛利持續惡化", "補貼政策大幅縮減"],
    },
    "cloud": {
        "investment_thesis": "企業雲端支出重啟成長，AI 服務為新動能，平台龍頭與具護城河 SaaS 公司為首選配置。",
        "profit_pools": [
            ProfitPool(position="基礎層 IaaS", margin_range="30-40%", pricing_power="強", bottleneck="低", companies="AWS, Azure, GCP"),
            ProfitPool(position="平台層 PaaS", margin_range="60-75%", pricing_power="中", bottleneck="低", companies="SNOW, DDOG"),
            ProfitPool(position="應用層 SaaS", margin_range="70-80%", pricing_power="中", bottleneck="低", companies="CRM, NOW"),
            ProfitPool(position="安全層", margin_range="65-75%", pricing_power="中", bottleneck="低", companies="CRWD, ZS"),
        ],
        "profit_pool_insight": "SaaS 毛利最高但成長減速；IaaS 毛利較低但規模優勢明顯；AI 整合能力成為新競爭力。",
        "benefit_pathway": "企業 IT 支出回升 → IaaS 需求成長 → PaaS 平台採用增加 → SaaS 訂閱擴張",
        "benefit_sequence": [
            BenefitStep(segment="IaaS 服務", tickers="AMZN, MSFT, GOOGL", trigger="企業上雲", timing="立即"),
            BenefitStep(segment="PaaS 平台", tickers="SNOW, DDOG", trigger="資料工作負載", timing="1-2 季"),
            BenefitStep(segment="SaaS 應用", tickers="CRM, NOW", trigger="數位轉型", timing="2-3 季"),
            BenefitStep(segment="雲端安全", tickers="CRWD, ZS", trigger="合規要求", timing="持續"),
        ],
        "kpi1_name": "雲端營收成長",
        "kpi2_name": "淨留存率",
        "kpi3_name": "FCF Margin",
        "industry_kpis": [
            IndustryKPI(name="公有雲市場規模", description="全球公有雲年度支出", current="~$600B (2024E)"),
            IndustryKPI(name="龍頭淨留存率 (NRR)", description="客戶擴張率", current="120-130%"),
            IndustryKPI(name="SaaS FCF Margin", description="自由現金流利潤率", current="20-30%"),
        ],
        "bull_triggers": ["企業 IT 支出加速成長", "AI 服務帶動 ARPU 上升", "獲利能力改善"],
        "bear_triggers": ["企業支出縮減", "雲端優化週期延長", "競爭壓價"],
        "base_assumptions": ["雲端支出穩健成長 15-20%", "AI 功能漸進式貢獻", "估值維持合理"],
        "bull_beneficiaries": "MSFT, AMZN — AI 整合與規模優勢",
        "bear_losers": "高估值成長股 — 支出縮減時估值壓縮",
        "conservative_picks": "MSFT, AMZN",
        "conservative_rationale": "雲端龍頭、AI 整合領先、財務穩健",
        "growth_picks": "CRWD, NOW",
        "growth_rationale": "特定領域龍頭、高成長高毛利",
        "aggressive_picks": "DDOG, SNOW",
        "aggressive_rationale": "估值較高但成長動能強",
        "upgrade_conditions": ["雲端支出加速成長", "AI 貢獻超預期"],
        "downgrade_conditions": ["企業 IT 支出大幅縮減", "淨留存率下滑"],
    },
}

# Default v2 content for themes not specifically defined
DEFAULT_V2_CONTENT = {
    "investment_thesis": "此產業趨勢值得關注，建議追蹤相關龍頭公司動態。",
    "profit_pools": [],
    "profit_pool_insight": "產業鏈各環節毛利結構請參考個別公司財報。",
    "benefit_pathway": "需求驅動 → 產業鏈傳導 → 相關公司受惠",
    "benefit_sequence": [],
    "kpi1_name": "營收成長",
    "kpi2_name": "毛利率",
    "kpi3_name": "市場規模",
    "industry_kpis": [],
    "bull_triggers": ["需求超預期成長", "政策利多"],
    "bear_triggers": ["需求放緩", "競爭加劇"],
    "base_assumptions": ["維持穩健成長"],
    "bull_beneficiaries": "產業龍頭",
    "bear_losers": "競爭力較弱者",
    "conservative_picks": "產業龍頭",
    "conservative_rationale": "規模與品牌優勢",
    "growth_picks": "高成長潛力股",
    "growth_rationale": "成長動能強勁",
    "aggressive_picks": "高風險高報酬標的",
    "aggressive_rationale": "波動大但潛力可期",
    "upgrade_conditions": ["需求加速成長"],
    "downgrade_conditions": ["需求明顯放緩"],
}


def get_stock_extended_metrics(
    fmp_client: Optional[FMPClient],
    ticker: str,
    spy_ytd: Optional[float] = None,
) -> dict:
    """Get extended metrics for a stock (v2).

    Returns dict with return_1d, return_1w, return_1m, return_ytd, vs_spy,
    pe, ev_sales, ev_ebitda, rev_growth, gross_margin.
    """
    metrics = {
        "return_1d": None,
        "return_1w": None,
        "return_1m": None,
        "return_ytd": None,
        "vs_spy": None,
        "pe": None,
        "ev_sales": None,
        "ev_ebitda": None,
        "rev_growth": None,
        "gross_margin": None,
    }

    if not fmp_client:
        return metrics

    try:
        # Get quote for price data
        quote = fmp_client.get_quote(ticker)
        if quote:
            change_pct = quote.get("changesPercentage", 0)
            if change_pct:
                metrics["return_1d"] = f"{change_pct:+.1f}%"

            pe = quote.get("pe")
            if pe:
                metrics["pe"] = f"{pe:.1f}x"

        # Get ratios for valuation metrics
        ratios = fmp_client.get_financial_ratios(ticker)
        if ratios:
            ev_sales = ratios.get("priceToSalesRatioTTM")
            if ev_sales:
                metrics["ev_sales"] = f"{ev_sales:.1f}x"

            ev_ebitda = ratios.get("enterpriseValueMultipleTTM")
            if ev_ebitda:
                metrics["ev_ebitda"] = f"{ev_ebitda:.1f}x"

        # Get key metrics for growth and margin
        key_metrics = fmp_client.get_key_metrics(ticker)
        if key_metrics:
            rev_growth = key_metrics.get("revenueGrowth")
            if rev_growth is not None:
                metrics["rev_growth"] = f"{rev_growth * 100:.1f}%"

            gross_margin = key_metrics.get("grossProfitMarginTTM")
            if gross_margin is not None:
                metrics["gross_margin"] = f"{gross_margin * 100:.1f}%"

        # Get historical prices for period returns
        historical = fmp_client.get_historical_price(
            ticker,
            from_date=date.today() - timedelta(days=40),
            to_date=date.today(),
        )
        if historical and len(historical) >= 5:
            current_price = historical[0].get("close", 0)
            # 1 week (5 trading days)
            if len(historical) >= 6:
                week_price = historical[5].get("close", 0)
                if week_price:
                    ret_1w = (current_price - week_price) / week_price * 100
                    metrics["return_1w"] = f"{ret_1w:+.1f}%"
            # 1 month (~21 trading days)
            if len(historical) >= 22:
                month_price = historical[21].get("close", 0)
                if month_price:
                    ret_1m = (current_price - month_price) / month_price * 100
                    metrics["return_1m"] = f"{ret_1m:+.1f}%"
            # YTD (find Jan 1 or closest)
            # Approximate with oldest price in range
            ytd_price = historical[-1].get("close", 0)
            if ytd_price:
                ret_ytd = (current_price - ytd_price) / ytd_price * 100
                metrics["return_ytd"] = f"{ret_ytd:+.1f}%"
                # vs SPY
                if spy_ytd is not None:
                    vs_spy = ret_ytd - spy_ytd
                    metrics["vs_spy"] = f"{vs_spy:+.1f}%"

    except Exception as e:
        logger.debug(f"Failed to get extended metrics for {ticker}: {e}")

    return metrics


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

    # Get theme content with fallback warning
    if theme_id in THEME_CONTENT:
        content = THEME_CONTENT[theme_id]
        logger.info(f"Using theme content for: {theme_id} ({theme.display_name})")
    else:
        logger.warning(f"Unknown theme '{theme_id}', falling back to ai-server content")
        content = THEME_CONTENT["ai-server"]
        # Override display to match fallback
        theme = DetectedTheme(
            theme_id="ai-server",
            display_name="AI 伺服器供應鏈",
            score=theme.score,
            matched_keywords=theme.matched_keywords,
            relevant_tickers=theme.relevant_tickers,
            trigger_events=theme.trigger_events,
        )

    # Get v2 content
    v2_content = THEME_CONTENT_V2.get(theme_id, DEFAULT_V2_CONTENT)

    # Get SPY YTD for relative performance calculation
    spy_ytd = None
    if fmp_client:
        try:
            spy_hist = fmp_client.get_historical_price(
                "SPY",
                from_date=date.today() - timedelta(days=40),
                to_date=date.today(),
            )
            if spy_hist and len(spy_hist) > 1:
                current = spy_hist[0].get("close", 0)
                oldest = spy_hist[-1].get("close", 0)
                if oldest:
                    spy_ytd = (current - oldest) / oldest * 100
        except Exception as e:
            logger.debug(f"Failed to get SPY YTD: {e}")

    # Get stock data for representative stocks with v2 metrics
    representative_stocks = []
    stock_data = content.get("stocks", [])

    for ticker, business, position, view in stock_data:
        market_cap = "--"
        company_name = ticker

        if fmp_client:
            cap = 0
            # Try profile first
            try:
                profile = fmp_client.get_company_profile(ticker)
                if profile:
                    cap = profile.get("mktCap", 0)
                    company_name = profile.get("companyName", ticker)
            except Exception as e:
                logger.debug(f"Profile fetch failed for {ticker}: {e}")

            # Fallback to quote if profile didn't have market cap
            if cap == 0:
                try:
                    quote = fmp_client.get_quote(ticker)
                    if quote:
                        cap = quote.get("marketCap", 0)
                        # Calculate from price * shares if still 0
                        if cap == 0:
                            price = quote.get("price", 0)
                            shares = quote.get("sharesOutstanding", 0)
                            if price and shares:
                                cap = price * shares
                except Exception as e:
                    logger.debug(f"Quote fetch failed for {ticker}: {e}")

            # Format market cap with consistent rounding (1 decimal for B, 2 for T)
            if cap >= 1_000_000_000_000:
                market_cap = f"${cap / 1_000_000_000_000:.2f}T"
            elif cap >= 1_000_000_000:
                # Use 1 decimal for billions for consistency
                market_cap = f"${cap / 1_000_000_000:.1f}B"
            elif cap >= 1_000_000:
                market_cap = f"${cap / 1_000_000:.0f}M"
            elif cap > 0:
                market_cap = f"${cap:,.0f}"

            if market_cap == "--":
                logger.warning(f"Could not get market cap for {ticker}")

        # v2: Get extended metrics
        ext_metrics = get_stock_extended_metrics(fmp_client, ticker, spy_ytd)

        representative_stocks.append(
            RepresentativeStock(
                ticker=ticker,
                name=company_name,
                market_cap=market_cap,
                business=business,
                position=position,
                view=view,
                # v2 fields
                return_1d=ext_metrics.get("return_1d"),
                return_1w=ext_metrics.get("return_1w"),
                return_1m=ext_metrics.get("return_1m"),
                return_ytd=ext_metrics.get("return_ytd"),
                vs_spy=ext_metrics.get("vs_spy"),
                pe=ext_metrics.get("pe"),
                ev_sales=ext_metrics.get("ev_sales"),
                ev_ebitda=ext_metrics.get("ev_ebitda"),
                rev_growth=ext_metrics.get("rev_growth"),
                gross_margin=ext_metrics.get("gross_margin"),
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

    # Theme-specific upcoming events (fix copy-paste bug)
    theme_events = {
        "ai-server": [
            {"date": "每季", "description": "雲端巨頭財報（MSFT, GOOGL, AMZN, META）"},
            {"date": "每季", "description": "NVDA 財報與資料中心營收"},
            {"date": "持續關注", "description": "AI 晶片供給與 CoWoS 產能"},
        ],
        "ai-software": [
            {"date": "每季", "description": "MSFT Copilot 與 Azure AI 營收貢獻"},
            {"date": "每季", "description": "企業軟體公司 AI 功能採用率"},
            {"date": "持續關注", "description": "AI 商業化進度與訂閱成長"},
        ],
        "semiconductor": [
            {"date": "每季", "description": "TSM 月營收與先進製程產能"},
            {"date": "每季", "description": "半導體設備訂單與交期"},
            {"date": "持續關注", "description": "庫存週期與終端需求"},
        ],
        "ev": [
            {"date": "每月/每季", "description": "TSLA/RIVN/LCID 交車量與 ASP"},
            {"date": "每週", "description": "車貸利率、二手 EV 殘值"},
            {"date": "政策面", "description": "補貼方案變動、關稅規則"},
        ],
        "cloud": [
            {"date": "每季", "description": "AWS/Azure/GCP 營收成長率"},
            {"date": "每季", "description": "SaaS 公司訂閱成長與留存率"},
            {"date": "持續關注", "description": "企業 IT 支出趨勢"},
        ],
        "biotech": [
            {"date": "持續關注", "description": "FDA 審批結果與臨床試驗進度"},
            {"date": "每季", "description": "GLP-1 藥物銷售數據"},
            {"date": "持續關注", "description": "併購動態與專利到期"},
        ],
        "fintech": [
            {"date": "每季", "description": "支付量與跨境交易成長"},
            {"date": "持續關注", "description": "加密貨幣監管政策"},
            {"date": "持續關注", "description": "消費支付趨勢"},
        ],
    }

    upcoming_events = theme_events.get(theme_id, [
        {"date": "每季", "description": "相關公司財報"},
        {"date": "持續關注", "description": "產業動態與政策變化"},
    ])

    # Add market cap timestamp with source
    # Detect weekend and use last trading day
    weekday = target_date.weekday()
    if weekday == 5:  # Saturday
        last_trading = target_date - __import__('datetime').timedelta(days=1)
        market_cap_as_of = f"{last_trading.strftime('%Y/%m/%d')} 美東收盤（來源：FMP API）"
    elif weekday == 6:  # Sunday
        last_trading = target_date - __import__('datetime').timedelta(days=2)
        market_cap_as_of = f"{last_trading.strftime('%Y/%m/%d')} 美東收盤（來源：FMP API）"
    else:
        market_cap_as_of = f"{target_date.strftime('%Y/%m/%d')} 美東收盤（來源：FMP API）"

    return Article3Evidence(
        date=target_date,
        theme=theme_id,
        theme_display=theme.display_name,
        why_now=why_now,
        drivers=drivers,
        supply_chain_overview=content["supply_chain_overview"],
        supply_chain=content["supply_chain"],
        representative_stocks=representative_stocks,
        market_cap_as_of=market_cap_as_of,
        bull_case=bull_case,
        base_case=content["base_case"],
        bear_case=bear_case,
        investment_strategy=investment_strategy,
        upcoming_events=upcoming_events,
        # v2 fields
        investment_thesis=v2_content.get("investment_thesis"),
        profit_pools=v2_content.get("profit_pools", []),
        profit_pool_insight=v2_content.get("profit_pool_insight"),
        benefit_pathway=v2_content.get("benefit_pathway"),
        benefit_sequence=v2_content.get("benefit_sequence", []),
        kpi1_name=v2_content.get("kpi1_name"),
        kpi2_name=v2_content.get("kpi2_name"),
        kpi3_name=v2_content.get("kpi3_name"),
        bull_triggers=v2_content.get("bull_triggers", []),
        bear_triggers=v2_content.get("bear_triggers", []),
        base_assumptions=v2_content.get("base_assumptions", []),
        bull_beneficiaries=v2_content.get("bull_beneficiaries"),
        bear_losers=v2_content.get("bear_losers"),
        conservative_picks=v2_content.get("conservative_picks"),
        conservative_rationale=v2_content.get("conservative_rationale"),
        growth_picks=v2_content.get("growth_picks"),
        growth_rationale=v2_content.get("growth_rationale"),
        aggressive_picks=v2_content.get("aggressive_picks"),
        aggressive_rationale=v2_content.get("aggressive_rationale"),
        industry_kpis=v2_content.get("industry_kpis", []),
        upgrade_conditions=v2_content.get("upgrade_conditions", []),
        downgrade_conditions=v2_content.get("downgrade_conditions", []),
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
