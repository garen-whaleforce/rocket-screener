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
