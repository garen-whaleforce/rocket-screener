"""Main entry point for Rocket Screener.

Usage:
    python -m app.run --date 2025-01-10 --dry-run
    python -m app.run --date 2025-01-10 --publish
"""

import argparse
import logging
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from app.config import TZ, load_config
from app.publish.publish_posts import ArticleContent, publish_articles

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("rocketscreener")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Rocket Screener - 獻給散戶的機構級分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date in YYYY-MM-DD format (default: today)",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate articles without publishing (output to out/)",
    )
    group.add_argument(
        "--publish",
        action="store_true",
        help="Generate and publish articles to Ghost",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="out",
        help="Output directory for dry-run mode (default: out)",
    )

    return parser.parse_args()


def get_target_date(date_str: Optional[str]) -> date:
    """Parse target date from string or return today."""
    if date_str:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    return datetime.now(TZ).date()


def generate_placeholder_articles(target_date: date) -> list[ArticleContent]:
    """Generate placeholder articles for v1 testing.

    In v2+, this will be replaced with real data from FMP/SEC/transcripts.
    """
    date_display = target_date.strftime("%Y/%m/%d")

    # Article 1: Daily Brief (placeholder)
    article1 = ArticleContent(
        article_num=1,
        title=f"美股盤後晨報 | {date_display}",
        markdown_content=f"""# 美股盤後晨報 | {date_display}

> {date_display} | 美股蓋倫哥

---

## 三行快讀

- 市場等待重要經濟數據公布
- 科技股表現分歧
- 債市維持穩定

---

## 市場快照

| 指標 | 收盤 | 漲跌 | 漲跌幅 |
|------|------|------|--------|
| S&P 500 | -- | -- | -- |
| Nasdaq | -- | -- | -- |
| 道瓊工業 | -- | -- | -- |
| 10Y 殖利率 | -- | -- | -- |
| 美元指數 | -- | -- | -- |
| 原油 (WTI) | -- | -- | -- |
| 黃金 | -- | -- | -- |
| BTC | -- | -- | -- |

---

## 今日焦點

> ⚠️ 這是測試版本，實際數據將在 v2 串接 FMP API 後呈現。

### 1. 測試事件一

**發生什麼事？**
這是一個 placeholder 事件。

**為何重要？**
測試文章模板結構。

**可能影響**
驗證 Ghost 發佈流程。

**下一步觀察**
確認 idempotent 機制正常。

📎 來源：[1](https://example.com)

---

## 今晚必看

- 經濟數據公布
- 企業財報發布
- Fed 官員談話

---

## 風險提示

本文內容僅供參考，不構成任何投資建議。投資有風險，入市需謹慎。過去績效不代表未來表現。

---

*Rocket Screener — 獻給散戶的機構級分析*
""",
        tags=["daily-brief", "market-update"],
        excerpt="每日美股盤後精選焦點，掌握市場脈動。",
    )

    # Article 2: Stock Deep Dive (placeholder)
    article2 = ArticleContent(
        article_num=2,
        title=f"個股深度｜NVDA 輝達：AI 晶片霸主的估值解析",
        slug_suffix="nvda",
        markdown_content=f"""# 個股深度｜NVDA 輝達：AI 晶片霸主的估值解析

> {date_display} | 美股蓋倫哥 | NVDA

---

## 公司概覽

NVIDIA（輝達）是全球領先的 GPU 與 AI 運算平台公司。

**關鍵數據**
- 市值：--
- 產業：科技 / 半導體
- 上市交易所：NASDAQ

---

## 基本面分析

> ⚠️ 這是測試版本，實際數據將在 v2 串接 FMP API 後呈現。

---

## 財務面分析

| 指標 | 最新季 | 前一季 | YoY |
|------|--------|--------|-----|
| 營收 | -- | -- | -- |
| 毛利率 | -- | -- | -- |
| 淨利 | -- | -- | -- |

---

## 估值分析

### 合理價推估

| 情境 | 假設 | 目標價 | 潛在空間 |
|------|------|--------|----------|
| 🐻 Bear | 成長放緩 | -- | -- |
| ⚖️ Base | 維持趨勢 | -- | -- |
| 🐂 Bull | 加速成長 | -- | -- |

---

## 催化劑與風險

### 潛在催化劑
- 資料中心需求持續成長
- 新產品發布

### 主要風險
- 競爭加劇
- 供應鏈限制

---

## 風險提示

本文內容僅供參考，不構成任何投資建議。投資有風險，入市需謹慎。過去績效不代表未來表現。作者可能持有或交易本文提及之股票。

---

*Rocket Screener — 獻給散戶的機構級分析*
""",
        tags=["deep-dive", "NVDA", "semiconductor", "AI"],
        excerpt="深入解析 NVIDIA 的基本面、財務與估值。",
    )

    # Article 3: Theme/Sector (placeholder)
    article3 = ArticleContent(
        article_num=3,
        title=f"產業趨勢｜AI 伺服器供應鏈：2025 關鍵趨勢",
        slug_suffix="ai-server",
        markdown_content=f"""# 產業趨勢｜AI 伺服器供應鏈：2025 關鍵趨勢

> {date_display} | 美股蓋倫哥 | AI 伺服器

---

## 為何現在關注？

AI 基礎設施需求持續攀升，帶動整體供應鏈受惠。

---

## 驅動因子

### 1. 算力需求爆發

大型語言模型訓練與推論需求持續成長。

### 2. 資料中心擴張

雲端服務商加速 capex 投入。

### 3. 技術迭代

先進封裝、HBM、CoWoS 等技術成為瓶頸與關鍵。

---

## 產業鏈結構

| 位置 | 環節 | 代表公司 | 說明 |
|------|------|----------|------|
| 上游 | GPU/ASIC | NVDA, AMD | 核心運算晶片 |
| 中游 | 封裝/記憶體 | TSM, SK Hynix | 先進製程與 HBM |
| 下游 | 伺服器組裝 | Dell, HPE | 系統整合 |

---

## 代表股票

| 股票 | 市值 | 核心業務 | 產業鏈位置 | 觀點 |
|------|------|----------|------------|------|
| NVDA | -- | GPU | 上游 | 龍頭 |
| AMD | -- | GPU/CPU | 上游 | 挑戰者 |
| TSM | -- | 晶圓代工 | 中游 | 關鍵供應商 |

---

## 情境展望

### 🐂 Bull Case
AI 需求超預期，供應鏈全線受惠。

### ⚖️ Base Case
穩健成長，符合市場預期。

### 🐻 Bear Case
需求放緩，庫存調整。

---

## 風險提示

本文內容僅供參考，不構成任何投資建議。投資有風險，入市需謹慎。過去績效不代表未來表現。

---

*Rocket Screener — 獻給散戶的機構級分析*
""",
        tags=["theme", "AI", "semiconductor", "supply-chain"],
        excerpt="解析 AI 伺服器供應鏈的關鍵趨勢與投資機會。",
    )

    return [article1, article2, article3]


def run(args: argparse.Namespace) -> int:
    """Main execution flow."""
    start_time = time.time()

    logger.info("=" * 60)
    logger.info("Rocket Screener 啟動")
    logger.info("=" * 60)

    # Get target date
    target_date = get_target_date(args.date)
    logger.info(f"目標日期: {target_date}")
    logger.info(f"模式: {'dry-run' if args.dry_run else 'publish'}")

    try:
        # Load configuration
        if args.publish:
            config = load_config()
            ghost_config = config.ghost
        else:
            # For dry-run, we don't need Ghost config
            ghost_config = None

        # Generate articles (v1: placeholder, v2+: real data)
        logger.info("生成文章...")
        articles = generate_placeholder_articles(target_date)
        logger.info(f"已生成 {len(articles)} 篇文章")

        # Publish or dry-run
        output_dir = Path(args.output_dir)
        results = publish_articles(
            articles=articles,
            target_date=target_date,
            config=ghost_config,
            dry_run=args.dry_run,
            output_dir=output_dir,
        )

        # Summary
        elapsed = time.time() - start_time
        logger.info("=" * 60)
        logger.info("執行完成")
        logger.info(f"耗時: {elapsed:.2f} 秒")
        for article_num, result in sorted(results.items()):
            status = result.get("status", "unknown")
            if status == "dry_run":
                logger.info(f"  文章 {article_num}: {result['md_path']}")
            elif status == "published":
                logger.info(f"  文章 {article_num}: {result['url']}")
                if result.get("newsletter_sent"):
                    logger.info(f"    -> Newsletter 已寄出")
            else:
                logger.error(f"  文章 {article_num}: {result.get('error', 'unknown error')}")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.exception(f"執行失敗: {e}")
        return 1


def main():
    """Entry point."""
    args = parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
