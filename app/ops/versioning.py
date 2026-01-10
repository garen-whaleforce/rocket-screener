"""Prompt and data versioning (v10).

Tracks versions of prompts, templates, and data for reproducibility.
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ArticleVersion:
    """Version info for a single article."""

    article_num: int
    date: str
    template_version: str
    prompt_version: str
    data_hash: str
    evidence_pack_hash: str
    generated_at: datetime


@dataclass
class DailyVersionRecord:
    """Complete version record for a day's run."""

    date: str
    run_id: str
    articles: list[ArticleVersion]
    config_hash: str
    app_version: str


def compute_hash(data: Any) -> str:
    """Compute SHA256 hash of data.

    Args:
        data: Data to hash (will be JSON serialized)

    Returns:
        Hex digest of hash
    """
    if isinstance(data, str):
        content = data
    else:
        content = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)

    return hashlib.sha256(content.encode()).hexdigest()[:16]


def get_template_version(template_path: Path) -> str:
    """Get version hash for a template.

    Args:
        template_path: Path to template file

    Returns:
        Version hash
    """
    try:
        content = template_path.read_text(encoding="utf-8")
        return compute_hash(content)
    except Exception:
        return "unknown"


def get_prompt_version(prompt_name: str) -> str:
    """Get version for a prompt.

    In production, prompts would be versioned files.

    Args:
        prompt_name: Name of the prompt

    Returns:
        Version string
    """
    # Placeholder - would read from prompts/ directory
    return "v1.0"


def create_version_record(
    date_str: str,
    articles: list[dict],  # Each with article_num, evidence_pack, etc.
    app_version: str = "0.1.0",
) -> DailyVersionRecord:
    """Create version record for a day's run.

    Args:
        date_str: Date string (YYYY-MM-DD)
        articles: List of article data dicts
        app_version: Application version

    Returns:
        Daily version record
    """
    import uuid

    run_id = str(uuid.uuid4())[:8]
    article_versions = []

    for article in articles:
        article_versions.append(
            ArticleVersion(
                article_num=article.get("article_num", 0),
                date=date_str,
                template_version=get_template_version(
                    Path(f"app/templates/article{article.get('article_num', 1)}.md")
                ),
                prompt_version=get_prompt_version(f"article{article.get('article_num', 1)}"),
                data_hash=compute_hash(article.get("evidence_pack", {})),
                evidence_pack_hash=compute_hash(article.get("evidence_pack", {})),
                generated_at=datetime.now(),
            )
        )

    return DailyVersionRecord(
        date=date_str,
        run_id=run_id,
        articles=article_versions,
        config_hash=compute_hash({}),  # Would hash actual config
        app_version=app_version,
    )


def save_version_record(record: DailyVersionRecord, output_dir: Path):
    """Save version record to file.

    Args:
        record: Version record to save
        output_dir: Output directory
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"version_{record.date}_{record.run_id}.json"

    data = {
        "date": record.date,
        "run_id": record.run_id,
        "config_hash": record.config_hash,
        "app_version": record.app_version,
        "articles": [
            {
                "article_num": a.article_num,
                "template_version": a.template_version,
                "prompt_version": a.prompt_version,
                "data_hash": a.data_hash,
                "generated_at": a.generated_at.isoformat(),
            }
            for a in record.articles
        ],
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"Version record saved: {path}")
    return path


def load_version_record(path: Path) -> Optional[dict]:
    """Load version record from file.

    Args:
        path: Path to version record

    Returns:
        Version record dict or None
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load version record: {e}")
        return None
