"""Tests for publishing module."""

from datetime import date

import pytest

from app.publish.publish_posts import generate_slug, markdown_to_html


class TestGenerateSlug:
    """Test slug generation."""

    def test_article1_slug(self):
        """Article 1 should have daily-brief prefix."""
        slug = generate_slug(1, date(2025, 1, 10))
        assert slug == "daily-brief-20250110"

    def test_article2_slug_with_ticker(self):
        """Article 2 should have equity-deep-dive prefix with ticker."""
        slug = generate_slug(2, date(2025, 1, 10), "NVDA")
        assert slug == "equity-deep-dive-20250110-nvda"

    def test_article3_slug_with_theme(self):
        """Article 3 should have theme-trend prefix with theme."""
        slug = generate_slug(3, date(2025, 1, 10), "AI Server")
        assert slug == "theme-trend-20250110-ai-server"

    def test_slug_normalizes_spaces(self):
        """Spaces in suffix should become hyphens."""
        slug = generate_slug(3, date(2025, 1, 10), "AI Semiconductor Supply Chain")
        assert slug == "theme-trend-20250110-ai-semiconductor-supply-chain"

    def test_slug_lowercase(self):
        """Suffix should be lowercased."""
        slug = generate_slug(2, date(2025, 1, 10), "AAPL")
        assert slug == "equity-deep-dive-20250110-aapl"


class TestMarkdownToHtml:
    """Test Markdown to HTML conversion."""

    def test_basic_conversion(self):
        """Basic markdown should convert to HTML."""
        md = "# Hello\n\nThis is a test."
        html = markdown_to_html(md)
        # toc extension adds id to headers
        assert "<h1" in html and "Hello</h1>" in html
        assert "<p>This is a test.</p>" in html

    def test_table_conversion(self):
        """Tables should be converted."""
        md = """
| Header | Value |
|--------|-------|
| Row 1  | A     |
"""
        html = markdown_to_html(md)
        assert "<table>" in html
        assert "<th>Header</th>" in html
        assert "<td>Row 1</td>" in html

    def test_code_block(self):
        """Code blocks should be converted."""
        md = "```python\nprint('hello')\n```"
        html = markdown_to_html(md)
        assert "<code>" in html or "<pre>" in html


class TestArticleContent:
    """Test ArticleContent structure."""

    def test_article_content_creation(self):
        """ArticleContent should be creatable with required fields."""
        from app.publish.publish_posts import ArticleContent

        article = ArticleContent(
            article_num=1,
            title="Test Title",
            markdown_content="# Test",
        )
        assert article.article_num == 1
        assert article.title == "Test Title"
        assert article.slug_suffix == ""
        assert article.tags is None
