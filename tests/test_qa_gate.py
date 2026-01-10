"""Tests for QA gate module."""

from datetime import date

import pytest

from app.ops.qa_gate import (
    check_disclaimer,
    check_sections,
    check_valuation,
    run_qa_gate,
)


class TestCheckDisclaimer:
    """Test disclaimer checking."""

    def test_has_disclaimer(self):
        """Should pass when disclaimer is present."""
        content = "Some content. 本文內容僅供參考，不構成任何投資建議。More content."
        errors = check_disclaimer(content, 1)
        assert len(errors) == 0

    def test_missing_disclaimer(self):
        """Should fail when disclaimer is missing."""
        content = "Some content without disclaimer."
        errors = check_disclaimer(content, 1)
        assert len(errors) == 1
        assert errors[0].code == "MISSING_DISCLAIMER"


class TestCheckSections:
    """Test section checking."""

    def test_article1_has_all_sections(self):
        """Article 1 with all sections should pass."""
        content = """
        # Title
        ## 三行快讀
        Quick summary
        ## 市場快照
        Market data
        ## 今日焦點
        Focus
        ## 風險提示
        Risk
        """
        errors = check_sections(content, 1)
        assert len(errors) == 0

    def test_article1_missing_section(self):
        """Article 1 missing section should fail."""
        content = """
        # Title
        ## 三行快讀
        Quick summary
        ## 今日焦點
        Focus
        """
        errors = check_sections(content, 1)
        assert len(errors) >= 1
        assert any("市場快照" in e.message for e in errors)


class TestCheckValuation:
    """Test valuation checking."""

    def test_article2_has_valuation_cases(self):
        """Article 2 with Bull/Base/Bear should pass."""
        content = """
        ## 估值分析
        🐂 Bull case
        ⚖️ Base case
        🐻 Bear case
        """
        errors = check_valuation(content, 2)
        assert len(errors) == 0

    def test_article2_missing_cases(self):
        """Article 2 without Bull/Base/Bear should fail."""
        content = """
        ## 估值分析
        Some valuation text
        """
        errors = check_valuation(content, 2)
        assert len(errors) == 1
        assert errors[0].code == "A2_MISSING_VALUATION_CASES"


class TestRunQAGate:
    """Test full QA gate run."""

    def test_all_pass(self):
        """All articles passing should result in pass status."""
        articles = [
            (1, """
            # 美股盤後晨報 | 2025/01/10
            ## 三行快讀
            test
            ## 市場快照
            test
            ## 今日焦點
            [1](https://example.com) [2](https://example.com) [3](https://example.com)
            [4](https://example.com) [5](https://example.com)
            ## 風險提示
            本文內容僅供參考，不構成任何投資建議
            """),
            (2, """
            # 個股深度
            ## 公司概覽
            test
            ## 基本面分析
            test
            ## 財務面
            test
            ## 估值分析
            🐂 Bull case
            ⚖️ Base case
            🐻 Bear case
            ## 風險提示
            本文內容僅供參考，不構成任何投資建議
            """),
            (3, """
            # 產業趨勢
            ## 為何現在關注
            test
            ## 驅動因子
            test
            ## 產業鏈
            test
            ## 代表股票
            test
            ## 情境展望
            test
            ## 風險提示
            本文內容僅供參考，不構成任何投資建議
            """),
        ]

        report = run_qa_gate(articles, date(2025, 1, 10))
        # May have warnings but no errors
        assert report.status == "pass" or len(report.errors) == 0

    def test_fail_on_missing_disclaimer(self):
        """Missing disclaimer should fail."""
        articles = [
            (1, "No disclaimer here"),
        ]

        report = run_qa_gate(articles, date(2025, 1, 10))
        assert report.status == "fail"
        assert any(e.code == "MISSING_DISCLAIMER" for e in report.errors)
