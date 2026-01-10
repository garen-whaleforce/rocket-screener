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

from app.config import TZ, AppConfig, FMPConfig, load_config
from app.publish.publish_posts import ArticleContent, publish_articles

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("rocketscreener")


# Universe: S&P 500 + hot stocks (will be loaded dynamically in v3+)
SEED_UNIVERSE = {
    # Mega caps
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA",
    "BRK.B", "JPM", "JNJ", "V", "UNH", "HD", "PG", "MA", "DIS",
    # Tech / AI
    "AMD", "INTC", "CRM", "ADBE", "NFLX", "PYPL", "AVGO", "QCOM",
    "MU", "AMAT", "LRCX", "KLAC", "ASML", "TSM", "ARM", "SMCI",
    # Other notable
    "COST", "WMT", "XOM", "CVX", "LLY", "NVO", "ABBV", "MRK", "PFE",
}


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
        help="Generate and publish articles to Ghost as drafts (default)",
    )
    group.add_argument(
        "--publish-live",
        action="store_true",
        help="Generate, publish and send newsletter (Article 1 only)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="out",
        help="Output directory for dry-run mode (default: out)",
    )

    parser.add_argument(
        "--no-fmp",
        action="store_true",
        help="Skip FMP API calls (use placeholder data)",
    )

    return parser.parse_args()


def get_target_date(date_str: Optional[str]) -> date:
    """Parse target date from string or return today."""
    if date_str:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    return datetime.now(TZ).date()


def generate_article1_with_fmp(
    target_date: date,
    fmp_config: FMPConfig,
) -> ArticleContent:
    """Generate Article 1 using FMP data."""
    from app.evidence.build_article1 import build_article1_evidence
    from app.features.event_scoring import score_events, select_top_events
    from app.ingest.fmp_client import FMPClient
    from app.llm.writer import render_article1
    from app.normalize.dedupe import deduplicate_news, filter_by_universe

    logger.info("正在從 FMP 取得資料...")

    fmp = FMPClient(fmp_config)

    # Get S&P 500 constituents and merge with seed
    try:
        sp500 = set(fmp.get_sp500_constituents())
        universe = SEED_UNIVERSE | sp500
        logger.info(f"Universe 大小: {len(universe)}")
    except Exception as e:
        logger.warning(f"無法取得 S&P 500 成分股: {e}")
        universe = SEED_UNIVERSE

    # Get news
    logger.info("取得新聞...")
    stock_news = fmp.get_stock_news(limit=100)
    general_news = fmp.get_general_news(limit=50)
    all_news = stock_news + general_news
    logger.info(f"取得 {len(all_news)} 則新聞")

    # Deduplicate
    events = deduplicate_news(all_news)

    # Filter by universe
    events = filter_by_universe(events, universe)

    # Get price changes for scoring
    price_changes = {}
    try:
        movers = fmp.get_gainers_losers()
        for item in movers.get("gainers", []) + movers.get("losers", []):
            symbol = item.get("symbol")
            change = item.get("changesPercentage", 0)
            if symbol:
                price_changes[symbol] = change
    except Exception as e:
        logger.warning(f"無法取得漲跌幅: {e}")

    # Score and select
    scored = score_events(events, price_changes)
    top_events = select_top_events(scored, min_count=5, max_count=8)

    # Build evidence pack with LLM analysis
    evidence = build_article1_evidence(target_date, fmp, top_events, price_changes)

    # Render article
    markdown = render_article1(evidence)

    return ArticleContent(
        article_num=1,
        title=f"美股盤後晨報 | {target_date.strftime('%Y/%m/%d')}",
        markdown_content=markdown,
        tags=["daily-brief", "market-update"],
        excerpt="每日美股盤後精選焦點，掌握市場脈動。",
    )


def generate_placeholder_article1(target_date: date) -> ArticleContent:
    """Generate placeholder Article 1 (no FMP)."""
    date_display = target_date.strftime("%Y/%m/%d")

    return ArticleContent(
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
| 原油 (WTI) | -- | -- | -- |
| 黃金 | -- | -- | -- |
| BTC | -- | -- | -- |

---

## 今日焦點

> ℹ️ 使用 --no-fmp 模式，顯示佔位內容。設定 FMP_API_KEY 環境變數以取得真實數據。

### 1. 市場觀望

**發生什麼事？**
投資者等待重要經濟數據公布。

**為何重要？**
數據將影響 Fed 利率決策方向。

**可能影響**
短期市場波動可能加劇。

**下一步觀察**
關注數據公布後的市場反應。

📎 來源：[1](https://example.com)

---

## 今晚必看

- 盤後財報公布動態
- 亞洲市場開盤反應
- 重要經濟數據公布

---

## 風險提示

本文內容僅供參考，不構成任何投資建議。投資有風險，入市需謹慎。過去績效不代表未來表現。

---

*Rocket Screener — 獻給散戶的機構級分析*
""",
        tags=["daily-brief", "market-update"],
        excerpt="每日美股盤後精選焦點，掌握市場脈動。",
    )


def generate_placeholder_article2(target_date: date) -> ArticleContent:
    """Generate placeholder Article 2 (will be real in v3)."""
    date_display = target_date.strftime("%Y/%m/%d")

    return ArticleContent(
        article_num=2,
        title="個股深度｜NVDA 輝達：AI 晶片霸主的估值解析",
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

> ℹ️ 完整數據將在 v3 版本呈現。

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


def generate_article2_with_fmp(
    target_date: date,
    fmp_config: FMPConfig,
    scored_events: list,
    price_changes: dict[str, float],
    ghost_config=None,
) -> ArticleContent:
    """Generate Article 2 using FMP data and hot stock scoring."""
    from app.evidence.build_article2 import build_article2_evidence
    from app.features.hot_stock_scoring import score_hot_stocks
    from app.features.valuation_chart import generate_valuation_chart_from_evidence
    from app.ingest.fmp_client import FMPClient
    from app.llm.writer import render_article2

    logger.info("生成文章 2：熱門股深度分析...")

    fmp = FMPClient(fmp_config)

    # Build news ticker counts from scored events
    news_ticker_counts = {}
    for ev in scored_events:
        for ticker in ev.event.tickers:
            news_ticker_counts[ticker] = news_ticker_counts.get(ticker, 0) + 1

    # Get universe
    try:
        sp500 = set(fmp.get_sp500_constituents())
        universe = SEED_UNIVERSE | sp500
    except Exception:
        universe = SEED_UNIVERSE

    # Score and select hot stock
    hot_stocks = score_hot_stocks(fmp, universe, news_ticker_counts)
    if not hot_stocks:
        logger.warning("無熱門股可選，使用預設")
        return generate_placeholder_article2(target_date)

    selected = hot_stocks[0]
    logger.info(f"選中熱門股: {selected.ticker} (score: {selected.score:.2f})")

    # Build evidence pack with transcript config if available
    from app.config import load_config as get_app_config

    app_config = get_app_config()
    transcript_config = app_config.transcript if app_config else None
    evidence = build_article2_evidence(target_date, fmp, selected, transcript_config)

    # Generate valuation chart (v4)
    chart_path = None
    chart_url = None
    try:
        output_dir = Path("out") / "charts" / target_date.strftime("%Y-%m-%d")
        chart_path = generate_valuation_chart_from_evidence(evidence, output_dir)
        if chart_path:
            logger.info(f"估值圖已生成: {chart_path}")
            # Upload to Ghost if config available
            if ghost_config:
                try:
                    from app.publish.ghost_client import GhostClient

                    ghost = GhostClient(ghost_config)
                    chart_url = ghost.upload_image(chart_path)
                    evidence.valuation_chart_url = chart_url
                    logger.info(f"估值圖已上傳: {chart_url}")
                except Exception as e:
                    logger.warning(f"估值圖上傳失敗: {e}")
    except Exception as e:
        logger.warning(f"估值圖生成失敗: {e}")

    # Render article
    markdown = render_article2(evidence)

    return ArticleContent(
        article_num=2,
        title=f"個股深度｜{selected.ticker} {selected.name}",
        slug_suffix=selected.ticker.lower(),
        markdown_content=markdown,
        tags=["deep-dive", selected.ticker, evidence.sector.lower()],
        excerpt=f"深入解析 {selected.name} 的基本面、財務與估值。",
    )


def generate_article3_with_fmp(
    target_date: date,
    fmp_config: FMPConfig,
    scored_events: list,
    output_dir: Path = None,
) -> ArticleContent:
    """Generate Article 3 using FMP data and theme detection."""
    from app.evidence.build_article3 import build_article3_evidence, generate_supply_chain_chart_for_article3
    from app.features.theme_detection import detect_themes
    from app.ingest.fmp_client import FMPClient
    from app.llm.writer import render_article3

    logger.info("生成文章 3：產業主題趨勢...")

    fmp = FMPClient(fmp_config)

    # Detect themes from events
    headlines = [e.event.headline for e in scored_events] if scored_events else []

    # Build ticker counts from events
    ticker_counts = {}
    for ev in scored_events:
        for ticker in ev.event.tickers:
            ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1

    themes = detect_themes(headlines, ticker_counts)

    if not themes:
        logger.warning("無主題可選，使用預設 AI 伺服器")
        from app.features.theme_detection import DetectedTheme

        themes = [DetectedTheme(
            theme_id="ai-server",
            display_name="AI 伺服器",
            score=1.0,
            matched_keywords=["AI"],
            relevant_tickers=["NVDA", "AMD", "TSM"],
            trigger_events=["AI 需求持續成長"],
        )]

    selected_theme = themes[0]
    logger.info(f"選中主題: {selected_theme.display_name}")

    # Build evidence pack with recent news for LLM
    evidence = build_article3_evidence(
        target_date, fmp, selected_theme, recent_news=headlines[:5]
    )

    # Generate supply chain chart (v8)
    if output_dir is None:
        output_dir = Path("output") / target_date.isoformat()
    chart_path = generate_supply_chain_chart_for_article3(evidence, output_dir)
    if chart_path:
        logger.info(f"產業鏈圖已生成: {chart_path}")

    # Render article
    markdown = render_article3(evidence)

    return ArticleContent(
        article_num=3,
        title=f"產業趨勢｜{selected_theme.display_name}",
        slug_suffix=selected_theme.theme_id,
        markdown_content=markdown,
        tags=["theme", selected_theme.theme_id],
        excerpt=f"解析 {selected_theme.display_name} 的關鍵趨勢與投資機會。",
    )


def generate_placeholder_article3(target_date: date) -> ArticleContent:
    """Generate placeholder Article 3 (fallback only)."""
    date_display = target_date.strftime("%Y/%m/%d")

    return ArticleContent(
        article_num=3,
        title="產業趨勢｜AI 伺服器供應鏈：2025 關鍵趨勢",
        slug_suffix="ai-server",
        markdown_content=f"""# 產業趨勢｜AI 伺服器供應鏈：2025 關鍵趨勢

> {date_display} | 美股蓋倫哥 | AI 伺服器

---

## 為何現在關注？

AI 基礎設施需求持續攀升，帶動整體供應鏈受惠。

---

## 風險提示

本文內容僅供參考，不構成任何投資建議。

---

*Rocket Screener — 獻給散戶的機構級分析*
""",
        tags=["theme", "AI", "semiconductor", "supply-chain"],
        excerpt="解析 AI 伺服器供應鏈的關鍵趨勢與投資機會。",
    )


def generate_articles(
    target_date: date,
    config: Optional[AppConfig],
    use_fmp: bool = True,
) -> list[ArticleContent]:
    """Generate all 3 articles.

    Args:
        target_date: Date for articles
        config: App configuration (None for dry-run without config)
        use_fmp: Whether to use FMP API

    Returns:
        List of 3 ArticleContent objects
    """
    from app.features.event_scoring import score_events, select_top_events
    from app.ingest.fmp_client import FMPClient
    from app.normalize.dedupe import deduplicate_news, filter_by_universe

    articles = []
    scored_events = []
    price_changes = {}

    # Get FMP data if available
    if use_fmp and config and config.fmp:
        try:
            fmp = FMPClient(config.fmp)

            # Get S&P 500 constituents and merge with seed
            try:
                sp500 = set(fmp.get_sp500_constituents())
                universe = SEED_UNIVERSE | sp500
            except Exception:
                universe = SEED_UNIVERSE

            # Get news
            stock_news = fmp.get_stock_news(limit=100)
            general_news = fmp.get_general_news(limit=50)
            all_news = stock_news + general_news

            # Deduplicate and filter
            events = deduplicate_news(all_news)
            events = filter_by_universe(events, universe)

            # Get price changes
            try:
                movers = fmp.get_gainers_losers()
                for item in movers.get("gainers", []) + movers.get("losers", []):
                    symbol = item.get("symbol")
                    change = item.get("changesPercentage", 0)
                    if symbol:
                        price_changes[symbol] = change
            except Exception:
                pass

            # Score events
            scored_events = score_events(events, price_changes)
            scored_events = select_top_events(scored_events, min_count=5, max_count=8)

            # Add SEC events (v6)
            try:
                from app.ingest.sec_client import SECClient

                sec_client = SECClient()
                # Check top tickers from scored events for SEC filings
                top_tickers = set()
                for ev in scored_events:
                    top_tickers.update(ev.event.tickers[:2])

                for ticker in list(top_tickers)[:10]:  # Limit API calls
                    sec_events = sec_client.detect_events(ticker, days_back=3)
                    for sec_ev in sec_events:
                        if sec_ev.importance == "high":
                            # Add SEC event to scored events
                            from app.normalize.dedupe import NewsEvent
                            from app.features.event_scoring import ScoredEvent

                            news_ev = NewsEvent(
                                headline=f"[SEC {sec_ev.form_type}] {ticker}: {sec_ev.description}",
                                text=f"{ticker} filed {sec_ev.form_type} with SEC on {sec_ev.filing_date}.",
                                tickers=[ticker],
                                source_urls=[sec_ev.url],
                                published_at=None,
                            )
                            sec_scored = ScoredEvent(
                                event=news_ev,
                                event_type="sec_filing",
                                score=0.7,
                                price_score=0,
                                recency_score=0.8,
                                novelty_score=0.6,
                            )
                            scored_events.append(sec_scored)
                            logger.info(f"Added SEC event: {sec_ev.form_type} for {ticker}")

                # Re-sort and limit
                scored_events = sorted(scored_events, key=lambda x: x.score, reverse=True)[:8]
            except Exception as e:
                logger.warning(f"SEC event detection failed: {e}")

        except Exception as e:
            logger.error(f"FMP 取得失敗: {e}")

    # Article 1: Daily Brief
    if use_fmp and config and config.fmp and scored_events:
        try:
            article1 = generate_article1_with_fmp(target_date, config.fmp)
        except Exception as e:
            logger.error(f"文章 1 生成失敗: {e}")
            article1 = generate_placeholder_article1(target_date)
    else:
        article1 = generate_placeholder_article1(target_date)

    articles.append(article1)

    # Article 2: Hot Stock Deep Dive
    if use_fmp and config and config.fmp:
        try:
            article2 = generate_article2_with_fmp(
                target_date, config.fmp, scored_events, price_changes,
                ghost_config=config.ghost if config else None
            )
        except Exception as e:
            logger.error(f"文章 2 生成失敗: {e}")
            article2 = generate_placeholder_article2(target_date)
    else:
        article2 = generate_placeholder_article2(target_date)

    articles.append(article2)

    # Article 3: Theme/Sector Trends
    if use_fmp and config and config.fmp:
        try:
            article3 = generate_article3_with_fmp(
                target_date, config.fmp, scored_events
            )
        except Exception as e:
            logger.error(f"文章 3 生成失敗: {e}")
            article3 = generate_placeholder_article3(target_date)
    else:
        article3 = generate_placeholder_article3(target_date)

    articles.append(article3)

    return articles


def run(args: argparse.Namespace) -> int:
    """Main execution flow."""
    start_time = time.time()

    logger.info("=" * 60)
    logger.info("Rocket Screener 啟動")
    logger.info("=" * 60)

    # Get target date
    target_date = get_target_date(args.date)
    logger.info(f"目標日期: {target_date}")

    # Determine mode
    if args.dry_run:
        mode = "dry-run"
    elif args.publish_live:
        mode = "publish-live (send newsletter)"
    else:
        mode = "publish (draft)"
    logger.info(f"模式: {mode}")

    try:
        # Load configuration
        config = None
        ghost_config = None

        if args.publish or args.publish_live:
            config = load_config()
            ghost_config = config.ghost
        elif not args.no_fmp:
            # Try to load FMP config for dry-run
            try:
                config = load_config()
            except Exception:
                logger.info("未設定環境變數，使用佔位內容")

        # Determine if we should use FMP
        use_fmp = not args.no_fmp and config is not None and config.fmp is not None

        # Generate articles
        logger.info("生成文章...")
        articles = generate_articles(target_date, config, use_fmp=use_fmp)
        logger.info(f"已生成 {len(articles)} 篇文章")

        # QA Gate (v9) - run before publishing
        from app.ops.qa_gate import run_qa_gate, save_qa_report

        qa_articles = [
            (a.article_num, a.markdown_content) for a in articles
        ]
        qa_report = run_qa_gate(qa_articles, target_date)

        output_dir = Path(args.output_dir)
        save_qa_report(qa_report, output_dir / target_date.strftime("%Y-%m-%d"))

        if qa_report.status == "fail" and not args.dry_run:
            logger.warning(f"QA Gate failed with {len(qa_report.errors)} errors")
            for error in qa_report.errors:
                logger.warning(f"  [{error.code}] Article {error.article_num}: {error.message}")
            # Send QA failure alert (v10)
            from app.ops.alerts import alert_on_qa_fail
            alert_on_qa_fail(qa_report.to_json())
            # Don't block, just warn - uncomment below to block publishing
            # raise ValueError(f"QA Gate failed: {len(qa_report.errors)} errors")
        else:
            logger.info(f"QA Gate: {qa_report.status.upper()} ({qa_report.passed}/{qa_report.articles_checked} passed)")

        # Publish or dry-run

        # Determine if publishing as draft (default) or live
        as_draft = not args.publish_live

        results = publish_articles(
            articles=articles,
            target_date=target_date,
            config=ghost_config,
            dry_run=args.dry_run,
            output_dir=output_dir,
            as_draft=as_draft,
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
            elif status in ("draft", "published"):
                status_label = "草稿" if status == "draft" else "已發佈"
                logger.info(f"  文章 {article_num} [{status_label}]: {result['url']}")
                if result.get("newsletter_sent"):
                    logger.info(f"    -> Newsletter 已寄出")
            else:
                logger.error(f"  文章 {article_num}: {result.get('error', 'unknown error')}")
        logger.info("=" * 60)

        # Success alert (v10) - only if configured
        from app.ops.alerts import alert_on_success
        alert_on_success()

        return 0

    except Exception as e:
        logger.exception(f"執行失敗: {e}")

        # Failure alert (v10)
        from app.ops.alerts import alert_on_failure
        alert_on_failure(
            error_message=str(e),
            details={"date": target_date.isoformat() if 'target_date' in dir() else None},
        )

        return 1


def main():
    """Entry point."""
    args = parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
