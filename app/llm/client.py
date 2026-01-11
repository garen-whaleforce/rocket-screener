"""LiteLLM client for content generation.

Uses LiteLLM unified proxy (OpenAI-compatible API).
Model: cli-gpt-5.2
"""

import logging
from typing import Optional

from openai import OpenAI

from app.config import LiteLLMConfig

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for LiteLLM unified proxy."""

    def __init__(self, config: LiteLLMConfig):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.api_url,
        )
        self.model = config.model

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2000,
    ) -> str:
        """Generate text using LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=1,  # GPT-5 models only support temperature=1
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise

    def translate_company_description(
        self,
        ticker: str,
        description: str,
    ) -> str:
        """Translate company description to Traditional Chinese.

        Args:
            ticker: Stock ticker
            description: English company description

        Returns:
            Traditional Chinese description
        """
        system_prompt = """你是專業的財經翻譯，將英文公司簡介翻譯成繁體中文（台灣用語）。
重要規則：
- 必須使用繁體中文，不可使用簡體中文
- 公司名稱保留英文原名
- 專有名詞和產品名稱保持準確
- 翻譯要簡潔、專業、易讀
- 只翻譯內容，不要加任何額外解釋"""

        prompt = f"""請將以下 {ticker} 公司簡介翻譯成繁體中文：

{description}

只回覆翻譯後的內容，不要其他文字。"""

        try:
            response = self.generate(prompt, system_prompt, max_tokens=800)
            return response.strip()
        except Exception as e:
            logger.warning(f"Company description translation failed: {e}")
            return description  # Return original if translation fails

    def translate_to_traditional_chinese(
        self,
        headline: str,
        what_happened: str,
    ) -> dict:
        """Translate English news headline and text to Traditional Chinese.

        Args:
            headline: English headline
            what_happened: English description of what happened

        Returns:
            Dict with headline_zh and what_happened_zh keys
        """
        system_prompt = """你是專業的財經翻譯，將英文財經新聞翻譯成繁體中文（台灣用語）。
重要規則：
- 必須使用繁體中文，不可使用簡體中文
- 股票代號保持英文（如 NVDA、AAPL）
- 公司名稱保留英文原名，可加中文翻譯
- 專有名詞保持準確（如 Fed、CPI、PCE）
- 翻譯要簡潔、流暢、專業"""

        prompt = f"""請將以下財經新聞翻譯成繁體中文：

【英文標題】
{headline}

【英文內容】
{what_happened}

請用以下 JSON 格式回覆：
{{
  "headline_zh": "繁體中文標題",
  "what_happened_zh": "繁體中文內容"
}}

只回覆 JSON，不要其他文字。"""

        try:
            response = self.generate(prompt, system_prompt, max_tokens=600)
            import json

            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            return json.loads(response.strip())
        except Exception as e:
            logger.warning(f"Translation failed: {e}")
            # Return original text if translation fails
            return {
                "headline_zh": headline,
                "what_happened_zh": what_happened,
            }

    def generate_event_analysis(
        self,
        headline: str,
        what_happened: str,
        related_tickers: list[str],
        price_changes: dict[str, float],
    ) -> dict:
        """Generate why_important, impact, and next_watch for an event.

        Args:
            headline: Event headline
            what_happened: Description of what happened
            related_tickers: List of related stock tickers
            price_changes: Dict of ticker -> price change %

        Returns:
            Dict with why_important, impact, next_watch keys
        """
        price_context = ""
        for ticker in related_tickers[:3]:
            if ticker in price_changes:
                change = price_changes[ticker]
                price_context += f"- {ticker}: {change:+.2f}%\n"

        system_prompt = """你是一位專業的美股分析師，為台灣投資人撰寫每日市場分析。
重要：所有回覆必須使用「繁體中文」（台灣用語），不可使用簡體中文。
你的風格：
- 簡潔有力，每段 1-2 句話
- 用白話文解釋專業概念
- 避免陳腔濫調和過度樂觀/悲觀
- 基於事實推論，不臆測"""

        prompt = f"""請針對以下新聞事件，生成三段分析：

【新聞標題】{headline}
【發生什麼事】{what_happened}
【相關股票】{', '.join(related_tickers[:5])}
【股價變化】
{price_context if price_context else "無資料"}

請用以下 JSON 格式回覆（繁體中文）：
{{
  "why_important": "為何這對投資人重要？（1-2句）",
  "impact": "可能的市場影響？（1-2句）",
  "next_watch": "投資人下一步該關注什麼？（1-2句）"
}}

只回覆 JSON，不要其他文字。"""

        try:
            response = self.generate(prompt, system_prompt, max_tokens=500)
            # Parse JSON from response
            import json

            # Handle potential markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            return json.loads(response.strip())
        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return {
                "why_important": "市場正在評估此事件的影響。",
                "impact": "影響程度待觀察。",
                "next_watch": "持續關注後續發展。",
            }

    def generate_stock_analysis(
        self,
        ticker: str,
        company_name: str,
        description: str,
        financials: list[dict],
        valuation: dict,
        price_change: float,
    ) -> dict:
        """Generate analysis sections for Article 2 (stock deep dive).

        Args:
            ticker: Stock ticker
            company_name: Company name
            description: Company description
            financials: List of financial metrics
            valuation: Valuation metrics
            price_change: Recent price change %

        Returns:
            Dict with analysis sections
        """
        financials_text = "\n".join(
            f"- {f['name']}: {f['current']}" for f in financials[:5]
        )

        system_prompt = """你是一位專業的美股分析師，為台灣投資人撰寫個股深度分析。
重要：所有回覆必須使用「繁體中文」（台灣用語），不可使用簡體中文。
你的風格：
- 專業但易懂
- 數據導向，但會解釋數據意義
- 平衡觀點，同時指出機會與風險
- 避免過度樂觀或悲觀"""

        prompt = f"""請針對以下個股，生成分析內容：

【股票】{ticker} - {company_name}
【公司簡介】{description[:300]}
【財務數據】
{financials_text}
【估值】P/E: {valuation.get('pe', 'N/A')}, Forward P/E: {valuation.get('forward_pe', 'N/A')}
【近期股價變化】{price_change:+.2f}%

請用以下 JSON 格式回覆（繁體中文）：
{{
  "investment_thesis": "投資論點（2-3句話概述為何值得關注）",
  "fundamental_analysis": "基本面重點（2-3句話）",
  "risk_factors": ["風險1", "風險2", "風險3"],
  "catalysts": ["催化劑1", "催化劑2", "催化劑3"],
  "outlook": "展望（1-2句話）"
}}

只回覆 JSON，不要其他文字。"""

        try:
            response = self.generate(prompt, system_prompt, max_tokens=800)
            import json

            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            return json.loads(response.strip())
        except Exception as e:
            logger.warning(f"Failed to parse stock analysis: {e}")
            return {
                "investment_thesis": "詳細分析請參考以下內容。",
                "fundamental_analysis": "基本面分析請參考財務數據。",
                "risk_factors": ["競爭加劇", "宏觀經濟風險", "產業週期風險"],
                "catalysts": ["新產品發布", "財報表現", "市場擴張"],
                "outlook": "持續關注後續發展。",
            }

    def generate_market_thesis(
        self,
        market_snapshot: list[dict],
        top_events_summary: list[str],
    ) -> str:
        """Generate 1-2 sentence market thesis for the day.

        Args:
            market_snapshot: List of market snapshot items
            top_events_summary: List of top event headlines

        Returns:
            1-2 sentence market thesis in Traditional Chinese
        """
        # Format market data
        market_text = "\n".join(
            f"- {m.get('symbol', '')}: {m.get('change_pct', 0):+.2f}%"
            for m in market_snapshot[:5]
        )
        events_text = "\n".join(f"- {e}" for e in top_events_summary[:5])

        system_prompt = """你是專業的美股分析師，擅長用 1-2 句話精準概括今日市場主線。
重要：必須使用繁體中文（台灣用語）。
風格：簡潔、專業、有觀點，像晨會開場白。"""

        prompt = f"""根據以下市場數據和重大事件，寫出今日市場主線（1-2 句話）：

【市場表現】
{market_text}

【重大事件】
{events_text}

直接回覆主線句子，不要其他文字。例如：
"科技股領漲，市場押注 AI 需求持續擴張；利率預期穩定，風險偏好回升。"
"""

        try:
            response = self.generate(prompt, system_prompt, max_tokens=150)
            # Remove quotes if present
            result = response.strip().strip('"').strip("'")
            return result
        except Exception as e:
            logger.warning(f"Failed to generate market thesis: {e}")
            return "市場觀望氣氛濃厚，等待關鍵數據與財報。"

    def generate_impact_card(
        self,
        headline: str,
        what_happened: str,
        related_tickers: list[str],
    ) -> dict:
        """Generate impact card for an event.

        Args:
            headline: Event headline
            what_happened: Event description
            related_tickers: Related stock tickers

        Returns:
            Dict with beneficiaries, losers, pricing_path, key_kpis
        """
        system_prompt = """你是專業的產業分析師，擅長分析事件的受益者/受害者和價格傳導。
重要：必須使用繁體中文（台灣用語）。
風格：簡潔精準，每項 1 句話內。"""

        prompt = f"""針對以下事件，分析影響：

【事件】{headline}
【詳情】{what_happened}
【相關股票】{', '.join(related_tickers[:5])}

用 JSON 格式回覆：
{{
  "beneficiaries": "受益股及理由（1句）",
  "losers": "受害股及理由（1句，若無則寫「暫無明顯受害者」）",
  "pricing_path": "價格傳導路徑（如：成本上升→轉嫁終端→毛利壓縮）",
  "key_kpis": "投資人應關注的 KPI（如：毛利率、ASP、訂單量）"
}}

只回覆 JSON。"""

        try:
            response = self.generate(prompt, system_prompt, max_tokens=300)
            import json

            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            return json.loads(response.strip())
        except Exception as e:
            logger.warning(f"Failed to generate impact card: {e}")
            return {
                "beneficiaries": "",
                "losers": "",
                "pricing_path": "",
                "key_kpis": "",
            }

    def generate_quick_hits(
        self,
        news_items: list[dict],
    ) -> list[dict]:
        """Generate quick hits (one-liner summaries) from news.

        Args:
            news_items: List of news items with title, ticker, change

        Returns:
            List of quick hit dicts with summary, ticker, change
        """
        # Format news for prompt
        news_text = "\n".join(
            f"- [{item.get('ticker', 'N/A')}] {item.get('title', '')}"
            for item in news_items[:20]
        )

        system_prompt = """你是財經快訊編輯，將英文新聞標題改寫成繁體中文一句話快訊。
風格：簡潔、口語化、有資訊量。每則 15-25 字內。"""

        prompt = f"""將以下新聞標題改寫成繁體中文快訊：

{news_text}

用 JSON 陣列格式回覆：
[
  {{"summary": "快訊內容", "ticker": "AAPL"}},
  {{"summary": "快訊內容", "ticker": "NVDA"}}
]

只回覆 JSON 陣列。"""

        try:
            response = self.generate(prompt, system_prompt, max_tokens=1000)
            import json

            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            return json.loads(response.strip())
        except Exception as e:
            logger.warning(f"Failed to generate quick hits: {e}")
            return []

    def generate_theme_analysis(
        self,
        theme: str,
        theme_display: str,
        representative_stocks: list[dict],
        recent_news: list[str],
    ) -> dict:
        """Generate analysis for Article 3 (theme/industry trends).

        Args:
            theme: Theme identifier
            theme_display: Display name for theme
            representative_stocks: List of representative stocks
            recent_news: Recent news headlines related to theme

        Returns:
            Dict with theme analysis sections
        """
        stocks_text = "\n".join(
            f"- {s['ticker']}: {s.get('business', '')}" for s in representative_stocks[:5]
        )
        news_text = "\n".join(f"- {n}" for n in recent_news[:5])

        system_prompt = """你是一位專業的產業分析師，為台灣投資人撰寫產業趨勢分析。
重要：所有回覆必須使用「繁體中文」（台灣用語），不可使用簡體中文。
你的風格：
- 宏觀視角，但能落地到個股
- 解釋產業驅動因子
- 平衡樂觀與風險
- 提供可操作的觀察重點"""

        prompt = f"""請針對以下產業主題，生成分析內容：

【主題】{theme_display}
【代表股票】
{stocks_text}
【近期相關新聞】
{news_text if news_text else "無特定新聞"}

請用以下 JSON 格式回覆（繁體中文）：
{{
  "why_now": "為何現在關注此主題？（2-3句話）",
  "drivers": [
    {{"title": "驅動因子1標題", "description": "說明（1-2句）"}},
    {{"title": "驅動因子2標題", "description": "說明（1-2句）"}},
    {{"title": "驅動因子3標題", "description": "說明（1-2句）"}}
  ],
  "bull_case": "樂觀情境（1-2句）",
  "bear_case": "悲觀情境（1-2句）",
  "investment_strategy": "投資策略建議（1-2句）"
}}

只回覆 JSON，不要其他文字。"""

        try:
            response = self.generate(prompt, system_prompt, max_tokens=800)
            import json

            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            return json.loads(response.strip())
        except Exception as e:
            logger.warning(f"Failed to parse theme analysis: {e}")
            return {
                "why_now": "此主題近期受到市場關注。",
                "drivers": [
                    {"title": "技術創新", "description": "新技術推動產業發展。"},
                    {"title": "需求成長", "description": "終端需求持續增加。"},
                    {"title": "政策支持", "description": "各國政策有利產業發展。"},
                ],
                "bull_case": "需求超預期，供應鏈全線受惠。",
                "bear_case": "需求放緩，庫存調整壓力。",
                "investment_strategy": "建議逢回布局龍頭股。",
            }


# Global client instance (lazy initialization)
_client: Optional[LLMClient] = None


def get_llm_client() -> Optional[LLMClient]:
    """Get or create LLM client instance."""
    global _client
    if _client is None:
        from app.config import load_config

        config = load_config()
        if config.litellm:
            _client = LLMClient(config.litellm)
            logger.info(f"LLM client initialized with model: {config.litellm.model}")
        else:
            logger.warning("LiteLLM not configured, LLM features disabled")
    return _client
