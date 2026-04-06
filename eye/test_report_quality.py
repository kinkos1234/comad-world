"""Tests for report generator — quality gate and helpers."""

from __future__ import annotations

from narration.report_generator import ReportGenerator


class TestQualityGate:
    def _make_generator(self) -> ReportGenerator:
        """Create ReportGenerator with no LLM (quality gate doesn't need it)."""
        return ReportGenerator(llm=None, analysis_dir="/tmp", output_dir="/tmp")

    def test_missing_section_detected(self):
        gen = self._make_generator()
        report = "# Title\n## 1. Executive Summary\nSome content.\n"
        issues = gen._quality_gate(report)
        # Should detect missing required sections
        missing = [i for i in issues if "필수 섹션 누락" in i]
        assert len(missing) > 0

    def test_all_sections_pass(self):
        gen = self._make_generator()
        required = [
            "Executive Summary", "인과 분석", "구조 분석",
            "시스템 다이내믹스", "교차 분석 인사이트",
            "시나리오 분석", "핵심 엔티티 프로파일",
            "리스크 매트릭스", "전략적 권고사항", "부록",
        ]
        report = "\n".join(f"## {s}\nContent here.\n" for s in required)
        # Pad to minimum length
        report += "\n" * 100 + "x" * 500
        issues = gen._quality_gate(report)
        missing = [i for i in issues if "필수 섹션 누락" in i]
        assert len(missing) == 0

    def test_short_report_detected(self):
        gen = self._make_generator()
        report = "Short."
        issues = gen._quality_gate(report)
        length_issues = [i for i in issues if "길이 부족" in i]
        assert len(length_issues) == 1

    def test_table_column_mismatch_detected(self):
        gen = self._make_generator()
        report = (
            "## Executive Summary\n"
            "## 인과 분석\n## 구조 분석\n## 시스템 다이내믹스\n"
            "## 교차 분석 인사이트\n## 시나리오 분석\n## 핵심 엔티티 프로파일\n"
            "## 리스크 매트릭스\n## 전략적 권고사항\n## 부록\n"
            "| Col1 | Col2 | Col3 |\n"
            "|------|------|------|\n"
            "| a | b |\n"  # Missing column
            "Some text after.\n"
            + "x" * 500
        )
        issues = gen._quality_gate(report)
        table_issues = [i for i in issues if "열 수 불일치" in i]
        assert len(table_issues) >= 1

    def test_hallucination_detection(self):
        gen = self._make_generator()
        report = (
            "## Executive Summary\n"
            "## 인과 분석\n## 구조 분석\n## 시스템 다이내믹스\n"
            "## 교차 분석 인사이트\n## 시나리오 분석\n## 핵심 엔티티 프로파일\n"
            "## 리스크 매트릭스\n## 전략적 권고사항\n## 부록\n"
            '```json\n{"leaked": true}\n```\n'
            + "x" * 500
        )
        issues = gen._quality_gate(report)
        artifact_issues = [i for i in issues if "아티팩트" in i]
        assert len(artifact_issues) >= 1

    def test_duplicate_sentence_detected(self):
        gen = self._make_generator()
        dup = "이 문장은 매우 중요한 인사이트를 담고 있습니다."
        report = (
            f"## Executive Summary\n{dup}\n### 종합 해석\ntest\n"
            f"## 인과 분석\n{dup}\n### 종합 해석\ntest\n"
            "## 구조 분석\n내용\n### 종합 해석\ntest\n"
            "## 시스템 다이내믹스\n내용\n### 종합 해석\ntest\n"
            "## 교차 분석 인사이트\n내용\n### 종합 해석\ntest\n"
            "## 시나리오 분석\n내용\n"
            "## 핵심 엔티티 프로파일\n내용\n"
            "## 리스크 매트릭스\n내용\n"
            "## 전략적 권고사항\n내용\n"
            "## 부록 A\n## 부록 B\n## 부록 C\n## 부록 D\n"
            + "x" * 500
        )
        issues = gen._quality_gate(report)
        dup_issues = [i for i in issues if "반복 문구" in i]
        assert len(dup_issues) >= 1

    def test_na_heavy_section_detected(self):
        gen = self._make_generator()
        report = (
            "## Executive Summary\n### 종합 해석\ntest\n"
            "## 인과 분석\n- N/A\n- 없음\n- N/A\n### 종합 해석\ntest\n"
            "## 구조 분석\n실제 데이터 있음\n### 종합 해석\ntest\n"
            "## 시스템 다이내믹스\n내용\n### 종합 해석\ntest\n"
            "## 교차 분석 인사이트\n내용\n### 종합 해석\ntest\n"
            "## 시나리오 분석\n내용\n"
            "## 핵심 엔티티 프로파일\n내용\n"
            "## 리스크 매트릭스\n내용\n"
            "## 전략적 권고사항\n내용\n"
            "## 부록 A\n## 부록 B\n## 부록 C\n## 부록 D\n"
            + "x" * 500
        )
        issues = gen._quality_gate(report)
        na_issues = [i for i in issues if "데이터 부족" in i]
        assert len(na_issues) >= 1


class TestPostProcess:
    def _make_generator(self) -> ReportGenerator:
        return ReportGenerator(llm=None, analysis_dir="/tmp", output_dir="/tmp")

    def test_underscore_to_space_korean(self):
        gen = self._make_generator()
        result = gen._post_process("한국_은행_총재")
        assert "한국 은행 총재" in result

    def test_json_key_cleanup(self):
        gen = self._make_generator()
        result = gen._post_process("downstream_count: 5")
        assert "하류 영향 수" in result

    def test_triple_newlines_collapsed(self):
        gen = self._make_generator()
        result = gen._post_process("line1\n\n\n\nline2")
        assert "\n\n\n" not in result


class TestHelpers:
    def test_clean_name_import(self):
        from narration.helpers import clean_name
        assert clean_name("entity_name_test") == "entity name test"

    def test_fmt_pct_import(self):
        from narration.helpers import fmt_pct
        assert fmt_pct(0.85) == "85%"
        assert fmt_pct(1.0) == "100%"

    def test_fmt_score_import(self):
        from narration.helpers import fmt_score
        assert fmt_score(0.12345) == "0.1235"
        assert fmt_score(0.12345, decimals=2) == "0.12"
