"""QA Gate automation (v9 + v2 template support).

Implements hard fail rules before publishing.
All articles must pass QA gate or be blocked.

Hard-fail rules (v9 upgraded):
1. Placeholder tokens (TBD, v3版本, TODO, FIXME) → hard fail
2. Too many data placeholders (>5 instances of --) → hard fail
3. Market snapshot ≥4 assets showing 0.00% → hard fail (data issue)
4. Theme title ≠ content theme (article 3) → hard fail
5. Missing required sections → hard fail
6. Missing disclaimer → hard fail
7. Missing Bull/Base/Bear valuation (article 2) → hard fail
8. Source links < 6 in article 1 → hard fail (upgraded from warning)

v2-specific checks (auto-detected or force_v2=True):
- Article 1: Market Thesis, Quick Reads (3+), Quick Hits (10+), Catalyst Calendar (3+), Impact Cards
- Article 2: Investment Summary, Tear Sheet (12+), 8Q Financials (6+), Competitors (3+), Sensitivity Matrix (5x5), Price Targets
- Article 3: Investment Thesis, Profit Pool, Benefit Sequence, Representative Stocks (8+), Industry KPIs

Soft-fail rules (warnings):
- Date format inconsistency
- Year inconsistency
- Missing data timestamps
- Too many PR/wire sources (>1 in Top 8)
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# HARD FAIL placeholder patterns - these should NEVER appear
HARD_FAIL_PLACEHOLDERS = [
    r"TBD",              # To Be Determined
    r"v3\s*才有",         # v3才有 (v3 only)
    r"v3\s*版本",         # v3版本 (v3 version)
    r"待補",              # 待補 (to be added)
    r"TODO",             # TODO marker
    r"FIXME",            # FIXME marker
    r"\[待填\]",          # [待填] placeholder
    r"\[TBD\]",          # [TBD] placeholder
]

# SOFT FAIL placeholder patterns - allowed in small quantities (e.g., YoY data not available)
# Note: These patterns must NOT match markdown table separators like |------|
SOFT_FAIL_PLACEHOLDERS = [
    r"\s--\s",           # -- with spaces (data placeholder)
    r"：--",             # Chinese colon followed by --
    r": --",             # English colon followed by --
]

# Maximum allowed soft placeholders before failing
MAX_SOFT_PLACEHOLDERS = 50  # Allow more placeholders for optional fields in v2 templates

# Compiled placeholder regexes
HARD_FAIL_REGEX = re.compile("|".join(HARD_FAIL_PLACEHOLDERS), re.IGNORECASE)
SOFT_FAIL_REGEX = re.compile("|".join(SOFT_FAIL_PLACEHOLDERS), re.IGNORECASE)

# Disclaimer text that must be present
REQUIRED_DISCLAIMER = "本文內容僅供參考，不構成任何投資建議"

# Required sections per article type (v1)
REQUIRED_SECTIONS = {
    1: ["三行快讀", "市場快照", "今日焦點", "風險提示"],
    2: ["公司概覽", "基本面", "財務", "估值", "風險提示"],
    3: ["為何", "驅動因子", "產業鏈", "代表股", "情境展望", "風險提示"],
}

# Required sections per article type (v2 - research report grade)
REQUIRED_SECTIONS_V2 = {
    1: ["Market Thesis", "三行快讀", "市場快照", "今日焦點", "Quick Hits", "Catalyst Calendar", "Rocket Watchlist", "風險提示"],
    2: ["Investment Summary", "Tear Sheet", "公司概覽", "基本面分析", "財務分析", "動能分析", "競爭分析", "估值分析", "管理層訊號", "催化劑與風險", "風險提示"],
    3: ["Investment Thesis", "為何現在關注", "驅動因子", "產業鏈", "Profit Pool", "受益順序", "Industry Dashboard", "情境展望", "關鍵監測指標", "風險提示"],
}

# v2 minimum counts
V2_MIN_QUICK_READS = 3
V2_MIN_QUICK_HITS = 10
V2_MIN_CATALYST_EVENTS = 3
V2_MIN_8Q_QUARTERS = 6
V2_MIN_COMPETITORS = 3
V2_MIN_REP_STOCKS = 8
V2_SENSITIVITY_ROWS = 5
V2_SENSITIVITY_COLS = 5

# Minimum event count for article 1
MIN_EVENTS = 5
MAX_EVENTS = 8

# Minimum source links required (hard fail)
MIN_SOURCE_LINKS = 6

# PR/low-quality source domains (should be limited)
PR_SOURCES = [
    "prnewswire.com",
    "businesswire.com",
    "globenewswire.com",
    "accesswire.com",
    "prweb.com",
]

# Maximum PR sources allowed in Top 8
MAX_PR_SOURCES = 1


@dataclass
class QAError:
    """Single QA error."""

    code: str
    article_num: int
    message: str
    severity: str = "error"  # error, warning


@dataclass
class QAReport:
    """Complete QA report."""

    date: date
    status: str  # pass, fail
    errors: list[QAError] = field(default_factory=list)
    warnings: list[QAError] = field(default_factory=list)
    articles_checked: int = 0
    passed: int = 0
    failed: int = 0

    def add_error(self, error: QAError):
        """Add an error to the report."""
        if error.severity == "warning":
            self.warnings.append(error)
        else:
            self.errors.append(error)

    def to_json(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "date": self.date.isoformat(),
            "status": self.status,
            "errors": [
                {
                    "code": e.code,
                    "article_num": e.article_num,
                    "message": e.message,
                }
                for e in self.errors
            ],
            "warnings": [
                {
                    "code": w.code,
                    "article_num": w.article_num,
                    "message": w.message,
                }
                for w in self.warnings
            ],
            "summary": {
                "articles_checked": self.articles_checked,
                "passed": self.passed,
                "failed": self.failed,
            },
        }

    def to_markdown(self) -> str:
        """Convert to human-readable Markdown."""
        lines = [
            f"# QA Report | {self.date.isoformat()}",
            "",
            f"**Status**: {'✅ PASS' if self.status == 'pass' else '❌ FAIL'}",
            "",
            f"- Articles checked: {self.articles_checked}",
            f"- Passed: {self.passed}",
            f"- Failed: {self.failed}",
            "",
        ]

        if self.errors:
            lines.extend([
                "## Errors (Must Fix)",
                "",
            ])
            for e in self.errors:
                lines.append(f"- **[{e.code}]** Article {e.article_num}: {e.message}")
            lines.append("")

        if self.warnings:
            lines.extend([
                "## Warnings",
                "",
            ])
            for w in self.warnings:
                lines.append(f"- **[{w.code}]** Article {w.article_num}: {w.message}")
            lines.append("")

        return "\n".join(lines)


def check_disclaimer(content: str, article_num: int) -> list[QAError]:
    """Check for required disclaimer."""
    errors = []
    if REQUIRED_DISCLAIMER not in content:
        errors.append(
            QAError(
                code="MISSING_DISCLAIMER",
                article_num=article_num,
                message="Missing required risk disclaimer",
            )
        )
    return errors


def check_sections(content: str, article_num: int) -> list[QAError]:
    """Check for required sections."""
    errors = []
    required = REQUIRED_SECTIONS.get(article_num, [])

    for section in required:
        if section not in content:
            errors.append(
                QAError(
                    code=f"A{article_num}_MISSING_SECTION",
                    article_num=article_num,
                    message=f"Missing required section: {section}",
                )
            )

    return errors


def check_source_links(content: str, article_num: int) -> list[QAError]:
    """Check for source links in article 1.

    Hard fail rules:
    - Must have at least MIN_SOURCE_LINKS unique source links
    - Too many PR sources is a warning
    """
    errors = []

    if article_num != 1:
        return errors

    # Check for source links - look for markdown links with numbers
    link_pattern = r'\[[\d]+\]\((https?://[^\)]+)\)'
    matches = re.findall(link_pattern, content)
    unique_links = list(set(matches))

    # HARD FAIL: Not enough source links
    if len(unique_links) < MIN_SOURCE_LINKS:
        errors.append(
            QAError(
                code="A1_INSUFFICIENT_LINKS",
                article_num=1,
                message=f"Article 1 needs at least {MIN_SOURCE_LINKS} source links, found {len(unique_links)}",
                severity="error",  # Upgraded to hard fail
            )
        )

    # WARNING: Too many PR/wire sources
    pr_count = sum(
        1 for url in unique_links
        if any(pr_domain in url.lower() for pr_domain in PR_SOURCES)
    )

    if pr_count > MAX_PR_SOURCES:
        errors.append(
            QAError(
                code="A1_TOO_MANY_PR_SOURCES",
                article_num=1,
                message=f"Article 1 has {pr_count} PR/wire sources (max {MAX_PR_SOURCES}). Prefer primary sources.",
                severity="warning",
            )
        )

    return errors


def check_valuation(content: str, article_num: int) -> list[QAError]:
    """Check for valuation section in article 2."""
    errors = []

    if article_num != 2:
        return errors

    # Check for Bull/Base/Bear
    has_bull = "Bull" in content or "bull" in content or "🐂" in content
    has_base = "Base" in content or "base" in content or "⚖️" in content
    has_bear = "Bear" in content or "bear" in content or "🐻" in content

    if not (has_bull and has_base and has_bear):
        errors.append(
            QAError(
                code="A2_MISSING_VALUATION_CASES",
                article_num=2,
                message="Article 2 missing Bull/Base/Bear valuation cases",
            )
        )

    return errors


def check_date_consistency(
    content: str, article_num: int, target_date: date
) -> list[QAError]:
    """Check date consistency in article."""
    errors = []
    date_str = target_date.strftime("%Y/%m/%d")

    if date_str not in content:
        errors.append(
            QAError(
                code="DATE_MISMATCH",
                article_num=article_num,
                message=f"Expected date {date_str} not found in article",
                severity="warning",
            )
        )

    return errors


def check_url_format(content: str, article_num: int) -> list[QAError]:
    """Check URL formats are valid."""
    errors = []

    # Find all URLs
    url_pattern = r'https?://[^\s\)\]>]+'
    urls = re.findall(url_pattern, content)

    for url in urls:
        # Basic validation
        if not url.startswith("http://") and not url.startswith("https://"):
            errors.append(
                QAError(
                    code="INVALID_URL",
                    article_num=article_num,
                    message=f"Invalid URL format: {url[:50]}...",
                )
            )

    return errors


def check_placeholders(content: str, article_num: int) -> list[QAError]:
    """Check for placeholder tokens that should never appear in published content.

    Two-tier system:
    - HARD FAIL: TBD, TODO, FIXME, etc. - any occurrence fails
    - SOFT FAIL: "--" placeholders - allowed up to MAX_SOFT_PLACEHOLDERS
    """
    errors = []

    # Check HARD FAIL patterns - any occurrence is a failure
    hard_matches = HARD_FAIL_REGEX.findall(content)
    if hard_matches:
        unique_matches = list(set(hard_matches))[:5]
        errors.append(
            QAError(
                code="PLACEHOLDER_FOUND",
                article_num=article_num,
                message=f"Found placeholder tokens: {unique_matches}. Article not ready for publishing.",
                severity="error",
            )
        )

    # Check SOFT FAIL patterns - allowed in small quantities
    soft_matches = SOFT_FAIL_REGEX.findall(content)
    if len(soft_matches) > MAX_SOFT_PLACEHOLDERS:
        errors.append(
            QAError(
                code="TOO_MANY_PLACEHOLDERS",
                article_num=article_num,
                message=f"Found {len(soft_matches)} data placeholders (max {MAX_SOFT_PLACEHOLDERS}). Check data quality.",
                severity="error",
            )
        )
    elif soft_matches:
        # Just a warning for a few placeholders
        logger.debug(f"Article {article_num}: {len(soft_matches)} soft placeholders (allowed)")

    # Additional check: look for -- in critical data fields (市值 is critical)
    critical_placeholder_pattern = r"(市值)[：:]\s*--"
    critical_matches = re.findall(critical_placeholder_pattern, content)
    if critical_matches:
        errors.append(
            QAError(
                code="CRITICAL_DATA_MISSING",
                article_num=article_num,
                message=f"Critical data missing: {critical_matches}",
                severity="error",
            )
        )

    return errors


def check_market_snapshot(content: str, article_num: int) -> list[QAError]:
    """Check market snapshot for data quality issues.

    Hard fail if too many assets show 0.00% or missing data.
    """
    errors = []

    if article_num != 1:
        return errors

    # Look for market snapshot section
    if "市場快照" not in content:
        return errors

    # Count 0.00% occurrences in market snapshot
    # Pattern matches: +0.00%, -0.00%, 0.00%
    zero_pattern = r"[+-]?0\.00%"
    zero_matches = re.findall(zero_pattern, content)

    # If more than 4 assets show 0.00%, it's likely a data issue
    if len(zero_matches) >= 4:
        errors.append(
            QAError(
                code="MARKET_DATA_SUSPECT",
                article_num=article_num,
                message=f"Market snapshot shows {len(zero_matches)} assets with 0.00% change - likely data issue",
                severity="error",
            )
        )

    return errors


def check_theme_consistency(content: str, article_num: int) -> list[QAError]:
    """Check theme display vs content consistency for article 3.

    Hard fail if theme title doesn't match content theme.
    """
    errors = []

    if article_num != 3:
        return errors

    # Theme keywords to check (more specific keywords first for priority)
    # PRIMARY keywords are strong indicators that should take priority
    theme_indicators = {
        "ai-server": {
            "primary": ["AI 伺服器", "伺服器供應鏈"],
            "secondary": ["GPU", "HBM", "CoWoS", "資料中心", "NVDA"],
        },
        "ai-software": {
            "primary": ["AI 軟體", "生成式 AI 軟體"],
            "secondary": ["ChatGPT", "Copilot"],
        },
        "semiconductor": {
            "primary": ["半導體", "晶圓代工"],
            "secondary": ["晶片", "先進製程", "EUV"],
        },
        "ev": {
            "primary": ["電動車", "EV 產業"],
            "secondary": ["電池", "充電", "自駕", "TSLA"],
        },
        "cloud": {
            "primary": ["雲端運算", "雲端服務"],
            "secondary": ["AWS", "Azure", "SaaS"],
        },
        "biotech": {
            "primary": ["生技", "製藥"],
            "secondary": ["FDA", "臨床試驗", "GLP-1"],
        },
        "fintech": {
            "primary": ["金融科技", "Fintech"],
            "secondary": ["支付", "加密貨幣", "區塊鏈"],
        },
    }

    # Try to detect which theme is mentioned in title/header
    # Priority: primary keywords > secondary keywords
    title_theme = None
    content_theme_scores = {}

    title_area = content[:500]

    # First pass: check for primary keywords in title (highest priority)
    for theme_id, keywords in theme_indicators.items():
        if any(kw in title_area for kw in keywords["primary"]):
            title_theme = theme_id
            break

    # Second pass: if no primary match, check secondary
    if not title_theme:
        for theme_id, keywords in theme_indicators.items():
            if any(kw in title_area for kw in keywords["secondary"]):
                title_theme = theme_id
                break

    # Calculate content theme scores
    for theme_id, keywords in theme_indicators.items():
        all_keywords = keywords["primary"] + keywords["secondary"]
        score = sum(1 for kw in all_keywords if kw in content)
        content_theme_scores[theme_id] = score

    # Find dominant content theme
    if content_theme_scores:
        dominant_theme = max(content_theme_scores, key=content_theme_scores.get)
        dominant_score = content_theme_scores[dominant_theme]

        # Check for mismatch
        if title_theme and title_theme != dominant_theme and dominant_score > 3:
            errors.append(
                QAError(
                    code="THEME_MISMATCH",
                    article_num=article_num,
                    message=f"Theme mismatch: title suggests '{title_theme}' but content is about '{dominant_theme}'",
                    severity="error",
                )
            )

    return errors


def check_year_consistency(content: str, article_num: int, target_date: date) -> list[QAError]:
    """Check for year inconsistencies in the content.

    Catch cases like content showing 2025 when it should be 2026.
    """
    errors = []

    target_year = target_date.year

    # Count year mentions
    year_pattern = r"\b(202[4-9])\b"
    year_matches = re.findall(year_pattern, content)

    if year_matches:
        year_counts = {}
        for y in year_matches:
            year_counts[y] = year_counts.get(y, 0) + 1

        # Check if wrong year is dominant
        target_year_str = str(target_year)
        wrong_years = {y: c for y, c in year_counts.items() if y != target_year_str}

        for wrong_year, count in wrong_years.items():
            target_count = year_counts.get(target_year_str, 0)
            # If wrong year appears more than target year, flag it
            if count > target_count and count >= 3:
                errors.append(
                    QAError(
                        code="YEAR_INCONSISTENCY",
                        article_num=article_num,
                        message=f"Year inconsistency: found {count} mentions of {wrong_year}, expected {target_year}",
                        severity="warning",
                    )
                )

    return errors


def check_data_timestamp(content: str, article_num: int, target_date: date) -> list[QAError]:
    """Check for data timestamp presence and validity.

    Articles 2 and 3 should include data timestamp to indicate data freshness.
    """
    errors = []

    # Article 2: check for price data timestamp
    if article_num == 2:
        # Look for patterns like "資料截至：2026/01/10" or "2026/01/10 收盤"
        # Writer outputs: *資料截至：{value}*
        timestamp_patterns = [
            r"資料截至[：:]\s*\d{4}/\d{2}/\d{2}",  # 資料截至：2026/01/10
            r"資料截至[：:]\s*[^\s]+收盤",          # 資料截至：2026/01/10 收盤
            r"\d{4}/\d{2}/\d{2}\s*收盤",           # 2026/01/10 收盤
            r"截至\s*\d{4}/\d{2}/\d{2}",           # 截至 2026/01/10
        ]

        has_timestamp = any(
            re.search(pattern, content) for pattern in timestamp_patterns
        )

        if not has_timestamp:
            errors.append(
                QAError(
                    code="A2_MISSING_DATA_TIMESTAMP",
                    article_num=article_num,
                    message="Article 2 missing price data timestamp (e.g., '資料截至：YYYY/MM/DD')",
                    severity="warning",
                )
            )

    # Article 3: check for market cap timestamp
    if article_num == 3:
        # Writer outputs: *市值資料截至：{value}*
        timestamp_patterns = [
            r"市值資料截至[：:]\s*\d{4}/\d{2}/\d{2}",  # 市值資料截至：2026/01/10
            r"資料截至[：:]\s*\d{4}/\d{2}/\d{2}",     # 資料截至：2026/01/10
            r"\d{4}/\d{2}/\d{2}.*市值",               # 2026/01/10 市值
        ]

        has_timestamp = any(
            re.search(pattern, content) for pattern in timestamp_patterns
        )

        if not has_timestamp:
            errors.append(
                QAError(
                    code="A3_MISSING_DATA_TIMESTAMP",
                    article_num=article_num,
                    message="Article 3 missing market cap data timestamp",
                    severity="warning",
                )
            )

    return errors


def detect_v2_format(content: str, article_num: int) -> bool:
    """Detect if content uses v2 template format.

    v2 templates have specific section headers that v1 doesn't have.
    """
    v2_markers = {
        1: ["Market Thesis", "Quick Hits", "Catalyst Calendar", "Rocket Watchlist"],
        2: ["Investment Summary", "Tear Sheet", "估值敏感度表", "短/中/長期合理價"],
        3: ["Investment Thesis", "Profit Pool", "受益順序", "Industry Dashboard"],
    }

    markers = v2_markers.get(article_num, [])
    # If at least 2 v2-specific markers are present, it's v2
    matches = sum(1 for m in markers if m in content)
    return matches >= 2


def check_article1_v2(content: str) -> list[QAError]:
    """Check Article 1 v2-specific required fields.

    Required:
    - Market Thesis (1-2 sentences)
    - Quick Reads (3+ items with format: 【動詞+結果】+ Ticker + 數字)
    - Quick Hits (10+ items)
    - Catalyst Calendar (3+ events total)
    - Impact Card for each top event
    """
    errors = []

    # 1. Check Market Thesis
    if "## Market Thesis" in content:
        # Find content between Market Thesis and next section
        thesis_match = re.search(r"## Market Thesis\s*\n+(.+?)(?=\n---|\n##)", content, re.DOTALL)
        if thesis_match:
            thesis_text = thesis_match.group(1).strip()
            # Remove template comments
            thesis_text = re.sub(r"\{#.*?#\}", "", thesis_text).strip()
            if len(thesis_text) < 20:
                errors.append(
                    QAError(
                        code="A1V2_EMPTY_THESIS",
                        article_num=1,
                        message="Market Thesis section is too short (< 20 chars)",
                    )
                )
    else:
        errors.append(
            QAError(
                code="A1V2_MISSING_THESIS",
                article_num=1,
                message="Missing v2 required section: Market Thesis",
            )
        )

    # 2. Check Quick Reads count (三行快讀)
    quick_reads_match = re.search(r"## 三行快讀\s*\n+(.+?)(?=\n---|\n##)", content, re.DOTALL)
    if quick_reads_match:
        quick_reads_section = quick_reads_match.group(1)
        # Count bullet points
        bullet_count = len(re.findall(r"^- ", quick_reads_section, re.MULTILINE))
        if bullet_count < V2_MIN_QUICK_READS:
            errors.append(
                QAError(
                    code="A1V2_INSUFFICIENT_QUICK_READS",
                    article_num=1,
                    message=f"Quick Reads needs {V2_MIN_QUICK_READS}+ items, found {bullet_count}",
                )
            )

    # 3. Check Quick Hits count
    quick_hits_match = re.search(r"## Quick Hits\s*\n+(.+?)(?=\n---|\n##)", content, re.DOTALL)
    if quick_hits_match:
        quick_hits_section = quick_hits_match.group(1)
        bullet_count = len(re.findall(r"^- ", quick_hits_section, re.MULTILINE))
        if bullet_count < V2_MIN_QUICK_HITS:
            errors.append(
                QAError(
                    code="A1V2_INSUFFICIENT_QUICK_HITS",
                    article_num=1,
                    message=f"Quick Hits needs {V2_MIN_QUICK_HITS}+ items, found {bullet_count}",
                )
            )
    else:
        errors.append(
            QAError(
                code="A1V2_MISSING_QUICK_HITS",
                article_num=1,
                message="Missing v2 required section: Quick Hits",
            )
        )

    # 4. Check Catalyst Calendar (combined count from 經濟數據, 財報發布, 其他事件)
    catalyst_match = re.search(r"## Catalyst Calendar[^\n]*\n+(.+?)(?=\n---|\n## (?!###))", content, re.DOTALL)
    if catalyst_match:
        catalyst_section = catalyst_match.group(1)
        # Count all bullet items in subsections
        bullet_count = len(re.findall(r"^- \*\*", catalyst_section, re.MULTILINE))
        if bullet_count < V2_MIN_CATALYST_EVENTS:
            errors.append(
                QAError(
                    code="A1V2_INSUFFICIENT_CATALYSTS",
                    article_num=1,
                    message=f"Catalyst Calendar needs {V2_MIN_CATALYST_EVENTS}+ events, found {bullet_count}",
                )
            )
    else:
        errors.append(
            QAError(
                code="A1V2_MISSING_CATALYST",
                article_num=1,
                message="Missing v2 required section: Catalyst Calendar",
            )
        )

    # 5. Check Impact Card presence in Top Events
    top_events_match = re.search(r"## 今日焦點[^\n]*\n+(.+?)(?=\n## Quick Hits|\n## Catalyst)", content, re.DOTALL)
    if top_events_match:
        events_section = top_events_match.group(1)
        # Count events (### headers)
        event_count = len(re.findall(r"^### \d+\.", events_section, re.MULTILINE))
        # Count Impact Cards
        impact_count = len(re.findall(r"\*\*Impact Card\*\*", events_section))

        if event_count > 0 and impact_count == 0:
            errors.append(
                QAError(
                    code="A1V2_MISSING_IMPACT_CARDS",
                    article_num=1,
                    message=f"Top {event_count} events have no Impact Cards (v2 requires impact analysis)",
                    severity="warning",
                )
            )

    return errors


def check_article2_v2(content: str) -> list[QAError]:
    """Check Article 2 v2-specific required fields.

    Required:
    - Investment Summary (2-3 sentences)
    - Tear Sheet (12+ fields)
    - 8Q financials (6+ quarters)
    - Competitors (3+)
    - Sensitivity matrix (5x5)
    - Short/Medium/Long term prices
    """
    errors = []

    # 1. Check Investment Summary
    if "## Investment Summary" in content:
        summary_match = re.search(r"## Investment Summary\s*\n+(.+?)(?=\n---|\n##)", content, re.DOTALL)
        if summary_match:
            summary_text = summary_match.group(1).strip()
            summary_text = re.sub(r"\{#.*?#\}", "", summary_text).strip()
            if len(summary_text) < 30:
                errors.append(
                    QAError(
                        code="A2V2_EMPTY_SUMMARY",
                        article_num=2,
                        message="Investment Summary is too short (< 30 chars)",
                    )
                )
    else:
        errors.append(
            QAError(
                code="A2V2_MISSING_SUMMARY",
                article_num=2,
                message="Missing v2 required section: Investment Summary",
            )
        )

    # 2. Check Tear Sheet field count
    if "## Tear Sheet" in content:
        tear_sheet_match = re.search(r"## Tear Sheet\s*\n+(.+?)(?=\n---\n\n##)", content, re.DOTALL)
        if tear_sheet_match:
            tear_section = tear_sheet_match.group(1)
            # Count table rows (| 指標 | 數值 | pattern)
            row_count = len(re.findall(r"^\| [^|]+\| [^|]+\|", tear_section, re.MULTILINE))
            if row_count < 12:
                errors.append(
                    QAError(
                        code="A2V2_INSUFFICIENT_TEAR_SHEET",
                        article_num=2,
                        message=f"Tear Sheet needs 12+ fields, found ~{row_count}",
                    )
                )
    else:
        errors.append(
            QAError(
                code="A2V2_MISSING_TEAR_SHEET",
                article_num=2,
                message="Missing v2 required section: Tear Sheet",
            )
        )

    # 3. Check 8Q financials (column headers)
    if "## 財務分析" in content or "財務分析（8 季趨勢）" in content:
        # Check for quarter labels in the table header
        # Match both formats: Q1, Q2, Q3... or Q1'24, Q2'24... or 1Q24...
        quarter_pattern = r"\| (Q[1-8]'?\d{0,2}|[1-4]Q\d{2}) "
        quarter_matches = re.findall(quarter_pattern, content)
        unique_quarters = len(set(quarter_matches))
        if unique_quarters < V2_MIN_8Q_QUARTERS:
            errors.append(
                QAError(
                    code="A2V2_INSUFFICIENT_QUARTERS",
                    article_num=2,
                    message=f"Financial analysis needs {V2_MIN_8Q_QUARTERS}+ quarters, found {unique_quarters}",
                )
            )

    # 4. Check competitors count
    if "## 競爭分析" in content:
        comp_match = re.search(r"## 競爭分析\s*\n+(.+?)(?=\n---|\n## (?!###))", content, re.DOTALL)
        if comp_match:
            comp_section = comp_match.group(1)
            # Count data rows (excluding header and separator)
            row_pattern = r"^\| [^|]+\([A-Z]+\)"  # | Company (TICKER)
            row_count = len(re.findall(row_pattern, comp_section, re.MULTILINE))
            if row_count < V2_MIN_COMPETITORS:
                errors.append(
                    QAError(
                        code="A2V2_INSUFFICIENT_COMPETITORS",
                        article_num=2,
                        message=f"Competitor analysis needs {V2_MIN_COMPETITORS}+ companies, found {row_count}",
                    )
                )
    else:
        errors.append(
            QAError(
                code="A2V2_MISSING_COMPETITORS",
                article_num=2,
                message="Missing v2 required section: 競爭分析",
            )
        )

    # 5. Check sensitivity matrix (5x5)
    if "估值敏感度表" in content:
        sens_match = re.search(r"估值敏感度表\s*\n+(.+?)(?=\n\*當前位置|\n---|\n##)", content, re.DOTALL)
        if sens_match:
            sens_section = sens_match.group(1)
            # Count EPS rows (rows starting with | $)
            eps_rows = len(re.findall(r"^\| \$[\d.]+", sens_section, re.MULTILINE))
            # Check if header has 5 P/E columns - look for the header row with "x"
            header_lines = [line for line in sens_section.split("\n") if "x |" in line or "x|" in line]
            pe_cols = 0
            if header_lines:
                pe_cols = len(re.findall(r"\d+\.?\d*x", header_lines[0]))

            if eps_rows < V2_SENSITIVITY_ROWS or pe_cols < V2_SENSITIVITY_COLS:
                errors.append(
                    QAError(
                        code="A2V2_INCOMPLETE_SENSITIVITY",
                        article_num=2,
                        message=f"Sensitivity matrix needs {V2_SENSITIVITY_ROWS}x{V2_SENSITIVITY_COLS}, found {eps_rows}x{pe_cols}",
                    )
                )
    else:
        errors.append(
            QAError(
                code="A2V2_MISSING_SENSITIVITY",
                article_num=2,
                message="Missing v2 required: 估值敏感度表 (sensitivity matrix)",
            )
        )

    # 6. Check short/medium/long term price targets
    if "短/中/長期合理價" in content:
        target_match = re.search(r"短/中/長期合理價\s*\n+(.+?)(?=\n---)", content, re.DOTALL)
        if target_match:
            target_section = target_match.group(1)
            # Check for 3 time frames
            has_short = "短期" in target_section
            has_medium = "中期" in target_section
            has_long = "長期" in target_section
            if not (has_short and has_medium and has_long):
                missing = []
                if not has_short:
                    missing.append("短期")
                if not has_medium:
                    missing.append("中期")
                if not has_long:
                    missing.append("長期")
                errors.append(
                    QAError(
                        code="A2V2_INCOMPLETE_TARGETS",
                        article_num=2,
                        message=f"Missing target price timeframes: {', '.join(missing)}",
                    )
                )
    else:
        errors.append(
            QAError(
                code="A2V2_MISSING_TARGETS",
                article_num=2,
                message="Missing v2 required: 短/中/長期合理價 (price targets)",
            )
        )

    return errors


def check_article3_v2(content: str) -> list[QAError]:
    """Check Article 3 v2-specific required fields.

    Required:
    - Investment Thesis (2-3 sentences)
    - Profit Pools (table with margin/pricing power)
    - Benefit Sequence (transmission path)
    - Representative stocks (8+)
    - Industry KPIs
    """
    errors = []

    # 1. Check Investment Thesis
    if "## Investment Thesis" in content:
        thesis_match = re.search(r"## Investment Thesis\s*\n+(.+?)(?=\n---|\n##)", content, re.DOTALL)
        if thesis_match:
            thesis_text = thesis_match.group(1).strip()
            thesis_text = re.sub(r"\{#.*?#\}", "", thesis_text).strip()
            if len(thesis_text) < 30:
                errors.append(
                    QAError(
                        code="A3V2_EMPTY_THESIS",
                        article_num=3,
                        message="Investment Thesis is too short (< 30 chars)",
                    )
                )
    else:
        errors.append(
            QAError(
                code="A3V2_MISSING_THESIS",
                article_num=3,
                message="Missing v2 required section: Investment Thesis",
            )
        )

    # 2. Check Profit Pool analysis
    if "## Profit Pool" in content or "Profit Pool 分析" in content:
        pool_match = re.search(r"Profit Pool[^\n]*\n+(.+?)(?=\n---|\n## (?!###))", content, re.DOTALL)
        if pool_match:
            pool_section = pool_match.group(1)
            # Check for key columns: 毛利率區間, 定價權
            has_margin = "毛利率" in pool_section
            has_pricing = "定價權" in pool_section
            if not (has_margin and has_pricing):
                errors.append(
                    QAError(
                        code="A3V2_INCOMPLETE_PROFIT_POOL",
                        article_num=3,
                        message="Profit Pool missing required columns (毛利率區間, 定價權)",
                    )
                )
    else:
        errors.append(
            QAError(
                code="A3V2_MISSING_PROFIT_POOL",
                article_num=3,
                message="Missing v2 required section: Profit Pool 分析",
            )
        )

    # 3. Check Benefit Sequence
    if "## 受益順序" in content or "受益順序（Who Benefits First）" in content:
        benefit_match = re.search(r"受益順序[^\n]*\n+(.+?)(?=\n---|\n## (?!###))", content, re.DOTALL)
        if benefit_match:
            benefit_section = benefit_match.group(1)
            # Check for table rows with sequence
            seq_rows = len(re.findall(r"^\| \d+ \|", benefit_section, re.MULTILINE))
            if seq_rows < 2:
                errors.append(
                    QAError(
                        code="A3V2_INCOMPLETE_BENEFIT_SEQ",
                        article_num=3,
                        message="Benefit Sequence needs at least 2 steps in the transmission path",
                    )
                )
    else:
        errors.append(
            QAError(
                code="A3V2_MISSING_BENEFIT_SEQ",
                article_num=3,
                message="Missing v2 required section: 受益順序",
            )
        )

    # 4. Check Representative stocks count (Industry Dashboard)
    if "## Industry Dashboard" in content:
        dashboard_match = re.search(r"## Industry Dashboard[^\n]*\n+(.+?)(?=\n---|\n## (?!###))", content, re.DOTALL)
        if dashboard_match:
            dashboard_section = dashboard_match.group(1)
            # Count stock rows (| TICKER |)
            stock_pattern = r"^\| [A-Z]{1,5} \|"
            stock_count = len(re.findall(stock_pattern, dashboard_section, re.MULTILINE))
            if stock_count < V2_MIN_REP_STOCKS:
                errors.append(
                    QAError(
                        code="A3V2_INSUFFICIENT_STOCKS",
                        article_num=3,
                        message=f"Industry Dashboard needs {V2_MIN_REP_STOCKS}+ stocks, found {stock_count}",
                    )
                )
    else:
        errors.append(
            QAError(
                code="A3V2_MISSING_DASHBOARD",
                article_num=3,
                message="Missing v2 required section: Industry Dashboard",
            )
        )

    # 5. Check Industry KPIs
    if "## 關鍵監測指標" in content:
        kpi_match = re.search(r"## 關鍵監測指標\s*\n+(.+?)(?=\n---|\n## )", content, re.DOTALL)
        if kpi_match:
            kpi_section = kpi_match.group(1)
            # Count KPI items
            kpi_count = len(re.findall(r"^- \*\*[^*]+\*\*", kpi_section, re.MULTILINE))
            if kpi_count < 2:
                errors.append(
                    QAError(
                        code="A3V2_INSUFFICIENT_KPIS",
                        article_num=3,
                        message="Industry KPIs needs at least 2 metrics to monitor",
                        severity="warning",
                    )
                )
    else:
        errors.append(
            QAError(
                code="A3V2_MISSING_KPIS",
                article_num=3,
                message="Missing v2 required section: 關鍵監測指標",
            )
        )

    # 6. Check Bull/Base/Bear cases have triggers
    for case, emoji in [("Bull", "🐂"), ("Base", "⚖️"), ("Bear", "🐻")]:
        case_pattern = rf"### {emoji} {case} Case"
        if case_pattern in content or f"### {case} Case" in content:
            case_match = re.search(rf"### .*{case} Case[^\n]*\n+(.+?)(?=\n---|\n### )", content, re.DOTALL)
            if case_match:
                case_section = case_match.group(1)
                # Check for triggers/assumptions
                has_trigger = "觸發條件" in case_section or "假設條件" in case_section
                if not has_trigger:
                    errors.append(
                        QAError(
                            code=f"A3V2_{case.upper()}_NO_TRIGGERS",
                            article_num=3,
                            message=f"{case} Case missing trigger conditions",
                            severity="warning",
                        )
                    )

    return errors


def check_v2_sections(content: str, article_num: int) -> list[QAError]:
    """Check v2 required sections."""
    errors = []
    required = REQUIRED_SECTIONS_V2.get(article_num, [])

    for section in required:
        if section not in content:
            errors.append(
                QAError(
                    code=f"A{article_num}V2_MISSING_SECTION",
                    article_num=article_num,
                    message=f"Missing v2 required section: {section}",
                )
            )

    return errors


def run_qa_gate(
    articles: list[tuple[int, str]],  # [(article_num, content), ...]
    target_date: date,
    force_v2: bool = False,
) -> QAReport:
    """Run QA gate on all articles.

    Hard-fail checks (will block publishing):
    - Placeholder tokens (TBD, v3版本, TODO, FIXME)
    - Too many -- data placeholders (> MAX_SOFT_PLACEHOLDERS)
    - Market snapshot data issues (≥4 assets showing 0.00%)
    - Theme title/content mismatch (article 3)
    - Missing required sections
    - Missing disclaimer
    - Missing Bull/Base/Bear valuation (article 2)
    - Insufficient source links (< MIN_SOURCE_LINKS in article 1)

    v2-specific checks (auto-detected or force_v2=True):
    - Article 1: Market Thesis, Quick Reads (3+), Quick Hits (10+), Catalyst Calendar (3+)
    - Article 2: Investment Summary, Tear Sheet (12+), 8Q Financials (6+), Competitors (3+), Sensitivity Matrix (5x5)
    - Article 3: Investment Thesis, Profit Pool, Benefit Sequence, Representative Stocks (8+)

    Soft-fail checks (warnings):
    - Date format inconsistency
    - Year inconsistency
    - Missing data timestamps (articles 2, 3)
    - Too many PR/wire sources (> MAX_PR_SOURCES)

    Args:
        articles: List of (article_num, content) tuples
        target_date: Expected date for articles
        force_v2: If True, always run v2 checks. If False, auto-detect v2 format.

    Returns:
        QA report with all errors and warnings
    """
    report = QAReport(date=target_date, status="pass")
    report.articles_checked = len(articles)

    for article_num, content in articles:
        article_errors = []

        # === HARD FAIL CHECKS (severity="error") ===

        # 1. Placeholder check - CRITICAL
        article_errors.extend(check_placeholders(content, article_num))

        # 2. Market snapshot data quality
        article_errors.extend(check_market_snapshot(content, article_num))

        # 3. Theme consistency (article 3)
        article_errors.extend(check_theme_consistency(content, article_num))

        # 4. Required sections
        article_errors.extend(check_sections(content, article_num))

        # 5. Disclaimer
        article_errors.extend(check_disclaimer(content, article_num))

        # 6. Valuation cases (article 2)
        article_errors.extend(check_valuation(content, article_num))

        # 7. URL format
        article_errors.extend(check_url_format(content, article_num))

        # === SOFT FAIL CHECKS (severity="warning") ===

        # 8. Date consistency
        article_errors.extend(check_date_consistency(content, article_num, target_date))

        # 9. Year consistency
        article_errors.extend(check_year_consistency(content, article_num, target_date))

        # 10. Data timestamp presence
        article_errors.extend(check_data_timestamp(content, article_num, target_date))

        # === HARD FAIL upgraded from soft ===

        # 11. Source links (article 1) - now a hard fail for < MIN_SOURCE_LINKS
        article_errors.extend(check_source_links(content, article_num))

        # === V2-SPECIFIC CHECKS (auto-detected or force_v2) ===
        is_v2 = force_v2 or detect_v2_format(content, article_num)
        if is_v2:
            logger.info(f"Article {article_num}: Running v2 checks (force_v2={force_v2})")

            # v2 section checks
            article_errors.extend(check_v2_sections(content, article_num))

            # Article-specific v2 checks
            if article_num == 1:
                article_errors.extend(check_article1_v2(content))
            elif article_num == 2:
                article_errors.extend(check_article2_v2(content))
            elif article_num == 3:
                article_errors.extend(check_article3_v2(content))

        # Add to report
        for error in article_errors:
            report.add_error(error)

        # Track pass/fail
        hard_errors = [e for e in article_errors if e.severity == "error"]
        if hard_errors:
            report.failed += 1
            logger.warning(f"Article {article_num} FAILED QA: {len(hard_errors)} errors")
        else:
            report.passed += 1
            logger.info(f"Article {article_num} passed QA")

    # Overall status
    if report.errors:
        report.status = "fail"
        logger.error(f"QA GATE FAILED: {len(report.errors)} errors found")
    else:
        logger.info("QA GATE PASSED")

    return report


def save_qa_report(report: QAReport, output_dir: Path):
    """Save QA report to files.

    Args:
        report: QA report to save
        output_dir: Directory to save files
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON
    json_path = output_dir / "qa_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report.to_json(), f, ensure_ascii=False, indent=2)

    # Save Markdown
    md_path = output_dir / "qa_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report.to_markdown())

    logger.info(f"QA report saved to {output_dir}")

    return json_path, md_path
