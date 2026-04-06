"""Tests for api/routes/report.py — report serving endpoint."""

from __future__ import annotations

from unittest.mock import patch

import pytest

fastapi = pytest.importorskip("fastapi", reason="fastapi not installed")
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api.server import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/report/{job_id}
# ---------------------------------------------------------------------------
class TestGetReport:
    def test_report_found_for_job_id(self, client, tmp_path):
        """When a job-specific report exists, return its content as markdown."""
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        expected_content = "# Report for job123\n\nKey findings..."
        (reports_dir / "job123.md").write_text(expected_content, encoding="utf-8")

        with patch("api.routes.report.REPORTS_DIR", reports_dir):
            resp = client.get("/api/report/job123")
            assert resp.status_code == 200
            assert resp.text == expected_content
            assert "text/markdown" in resp.headers.get("content-type", "")

    def test_report_fallback_to_default(self, client, tmp_path):
        """When job-specific report doesn't exist, fall back to report.md."""
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        fallback_content = "# Default Report\n\nGeneric findings..."
        (reports_dir / "report.md").write_text(fallback_content, encoding="utf-8")

        with patch("api.routes.report.REPORTS_DIR", reports_dir):
            resp = client.get("/api/report/nonexistent_job")
            assert resp.status_code == 200
            assert resp.text == fallback_content

    def test_report_not_found_returns_404(self, client, tmp_path):
        """When no report exists at all, return 404."""
        reports_dir = tmp_path / "empty_reports"
        reports_dir.mkdir()

        with patch("api.routes.report.REPORTS_DIR", reports_dir):
            resp = client.get("/api/report/missing_job")
            assert resp.status_code == 404
            assert "not found" in resp.json()["detail"].lower()

    def test_report_content_type_is_markdown(self, client, tmp_path):
        """Response should have text/markdown content type."""
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        (reports_dir / "mdjob.md").write_text("# Test", encoding="utf-8")

        with patch("api.routes.report.REPORTS_DIR", reports_dir):
            resp = client.get("/api/report/mdjob")
            assert resp.status_code == 200
            assert "text/markdown" in resp.headers["content-type"]

    def test_report_with_unicode_content(self, client, tmp_path):
        """Report with Korean text should be returned correctly."""
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        content = "# 분석 리포트\n\n주요 발견사항: 경제적 영향이 크다."
        (reports_dir / "korean_job.md").write_text(content, encoding="utf-8")

        with patch("api.routes.report.REPORTS_DIR", reports_dir):
            resp = client.get("/api/report/korean_job")
            assert resp.status_code == 200
            assert "분석 리포트" in resp.text
            assert "경제적 영향" in resp.text

    def test_report_empty_file(self, client, tmp_path):
        """An empty report file should return 200 with empty body."""
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        (reports_dir / "empty_job.md").write_text("", encoding="utf-8")

        with patch("api.routes.report.REPORTS_DIR", reports_dir):
            resp = client.get("/api/report/empty_job")
            assert resp.status_code == 200
            assert resp.text == ""

    def test_report_job_specific_takes_priority(self, client, tmp_path):
        """When both job-specific and default report exist, job-specific wins."""
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        (reports_dir / "priority_job.md").write_text("JOB SPECIFIC", encoding="utf-8")
        (reports_dir / "report.md").write_text("DEFAULT", encoding="utf-8")

        with patch("api.routes.report.REPORTS_DIR", reports_dir):
            resp = client.get("/api/report/priority_job")
            assert resp.status_code == 200
            assert resp.text == "JOB SPECIFIC"

    def test_report_large_file(self, client, tmp_path):
        """Large report files should be served correctly."""
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        large_content = "# Large Report\n\n" + ("Paragraph text. " * 1000 + "\n\n") * 50
        (reports_dir / "large_job.md").write_text(large_content, encoding="utf-8")

        with patch("api.routes.report.REPORTS_DIR", reports_dir):
            resp = client.get("/api/report/large_job")
            assert resp.status_code == 200
            assert len(resp.text) > 10000
