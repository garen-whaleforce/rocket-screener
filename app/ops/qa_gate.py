"""QA Gate automation (v9).

Implements hard fail rules before publishing.
All articles must pass QA gate or be blocked.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Disclaimer text that must be present
REQUIRED_DISCLAIMER = "本文內容僅供參考，不構成任何投資建議"

# Required sections per article type
REQUIRED_SECTIONS = {
    1: ["三行快讀", "市場快照", "今日焦點", "風險提示"],
    2: ["公司概覽", "基本面", "財務", "估值", "風險提示"],
    3: ["為何", "驅動因子", "產業鏈", "代表股", "情境展望", "風險提示"],
}

# Minimum event count for article 1
MIN_EVENTS = 5
MAX_EVENTS = 8


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
    """Check for source links in article 1."""
    errors = []

    if article_num != 1:
        return errors

    # Check for source links
    link_pattern = r'\[[\d]+\]\(https?://[^\)]+\)'
    links = re.findall(link_pattern, content)

    if len(links) < MIN_EVENTS:
        errors.append(
            QAError(
                code="A1_INSUFFICIENT_LINKS",
                article_num=1,
                message=f"Article 1 needs at least {MIN_EVENTS} source links, found {len(links)}",
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


def run_qa_gate(
    articles: list[tuple[int, str]],  # [(article_num, content), ...]
    target_date: date,
) -> QAReport:
    """Run QA gate on all articles.

    Args:
        articles: List of (article_num, content) tuples
        target_date: Expected date for articles

    Returns:
        QA report with all errors and warnings
    """
    report = QAReport(date=target_date, status="pass")
    report.articles_checked = len(articles)

    for article_num, content in articles:
        article_errors = []

        # Run all checks
        article_errors.extend(check_disclaimer(content, article_num))
        article_errors.extend(check_sections(content, article_num))
        article_errors.extend(check_source_links(content, article_num))
        article_errors.extend(check_valuation(content, article_num))
        article_errors.extend(check_date_consistency(content, article_num, target_date))
        article_errors.extend(check_url_format(content, article_num))

        # Add to report
        for error in article_errors:
            report.add_error(error)

        # Track pass/fail
        hard_errors = [e for e in article_errors if e.severity == "error"]
        if hard_errors:
            report.failed += 1
        else:
            report.passed += 1

    # Overall status
    if report.errors:
        report.status = "fail"

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
