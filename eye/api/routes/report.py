"""Report routes — serve generated markdown reports."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

router = APIRouter()

REPORTS_DIR = Path("data/reports")


@router.get("/report/{job_id}")
async def get_report(job_id: str):
    """Return the generated report as markdown text."""
    # Try job-specific report first, then fallback to default
    report_path = REPORTS_DIR / f"{job_id}.md"
    if not report_path.exists():
        report_path = REPORTS_DIR / "report.md"

    if not report_path.exists():
        raise HTTPException(404, "Report not found")

    content = report_path.read_text(encoding="utf-8")
    return PlainTextResponse(content, media_type="text/markdown")
