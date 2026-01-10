"""Publish articles to Ghost CMS.

Handles the publishing workflow for all 3 daily articles:
- Article 1: Morning brief (sends newsletter)
- Article 2: Stock deep dive (no newsletter)
- Article 3: Theme/sector analysis (no newsletter)
"""

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import markdown

from app.config import GhostConfig
from app.publish.ghost_client import GhostClient, Post

logger = logging.getLogger(__name__)


@dataclass
class ArticleContent:
    """Content for a single article."""

    article_num: int  # 1, 2, or 3
    title: str
    markdown_content: str
    slug_suffix: str = ""  # e.g., ticker for article 2, theme for article 3
    tags: Optional[list[str]] = None
    feature_image_path: Optional[str] = None
    excerpt: Optional[str] = None


def generate_slug(article_num: int, target_date: date, suffix: str = "") -> str:
    """Generate unique slug for an article.

    Format: {type}-{YYYYMMDD}[-{suffix}]

    Examples:
    - daily-brief-20250110
    - equity-deep-dive-20250110-nvda
    - theme-trend-20250110-ai-semiconductors
    """
    date_str = target_date.strftime("%Y%m%d")

    if article_num == 1:
        base = f"daily-brief-{date_str}"
    elif article_num == 2:
        base = f"equity-deep-dive-{date_str}"
    else:
        base = f"theme-trend-{date_str}"

    if suffix:
        # Normalize suffix for URL
        normalized = suffix.lower().replace(" ", "-").replace("_", "-")
        return f"{base}-{normalized}"

    return base


def markdown_to_html(md_content: str) -> str:
    """Convert Markdown to HTML for Ghost.

    Uses extensions for tables, code highlighting, etc.
    """
    extensions = [
        "tables",
        "fenced_code",
        "codehilite",
        "toc",
        "nl2br",
    ]

    html = markdown.markdown(md_content, extensions=extensions)
    return html


def publish_articles(
    articles: list[ArticleContent],
    target_date: date,
    config: GhostConfig,
    dry_run: bool = False,
    output_dir: Optional[Path] = None,
) -> dict[int, dict]:
    """Publish articles to Ghost.

    Args:
        articles: List of article contents
        target_date: Date for the articles
        config: Ghost configuration
        dry_run: If True, only write to output_dir without publishing
        output_dir: Directory to write output files (required for dry_run)

    Returns:
        Dict mapping article_num to publish result
    """
    results = {}

    if dry_run:
        if output_dir is None:
            output_dir = Path("out")
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Dry run mode: writing to {output_dir}")

    client = None
    if not dry_run:
        client = GhostClient(config)

    # Sort articles: publish 2 and 3 first, then 1 (which sends newsletter)
    # This ensures newsletter links to already-published articles
    sorted_articles = sorted(articles, key=lambda a: (a.article_num == 1, a.article_num))

    for article in sorted_articles:
        slug = generate_slug(
            article.article_num, target_date, article.slug_suffix
        )

        html_content = markdown_to_html(article.markdown_content)

        post = Post(
            title=article.title,
            slug=slug,
            html=html_content,
            status="published",
            tags=article.tags,
            excerpt=article.excerpt,
        )

        if dry_run:
            # Write to file
            md_path = output_dir / f"article{article.article_num}.md"
            html_path = output_dir / f"article{article.article_num}.html"

            md_path.write_text(article.markdown_content, encoding="utf-8")
            html_path.write_text(html_content, encoding="utf-8")

            logger.info(f"[DRY RUN] Article {article.article_num}: {md_path}")
            results[article.article_num] = {
                "status": "dry_run",
                "slug": slug,
                "md_path": str(md_path),
                "html_path": str(html_path),
            }
        else:
            # Publish to Ghost
            # Only article 1 sends newsletter
            send_newsletter = article.article_num == 1

            try:
                # Upload feature image if provided
                feature_image_url = None
                if article.feature_image_path and Path(article.feature_image_path).exists():
                    feature_image_url = client.upload_image(article.feature_image_path)
                    post.feature_image = feature_image_url

                result = client.publish_post_idempotent(
                    post=post,
                    send_newsletter=send_newsletter,
                )

                results[article.article_num] = {
                    "status": "published",
                    "id": result["id"],
                    "slug": result["slug"],
                    "url": result["url"],
                    "newsletter_sent": send_newsletter and result.get("email"),
                }

                logger.info(
                    f"Published article {article.article_num}: {result['url']}"
                )
                if send_newsletter:
                    logger.info(f"  Newsletter: {'sent' if result.get('email') else 'not sent (already sent or disabled)'}")

            except Exception as e:
                logger.error(f"Failed to publish article {article.article_num}: {e}")
                results[article.article_num] = {
                    "status": "error",
                    "error": str(e),
                }
                raise

    return results
