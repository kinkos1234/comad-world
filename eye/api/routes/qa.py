"""Q&A routes — conversational Q&A over analysis results."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from api.models import QARequest, QAResponse
from comad_eye.config import load_settings

router = APIRouter()
logger = logging.getLogger("comadeye")

# Per-job QA sessions
_sessions: dict[str, Any] = {}


@router.post("/qa/ask")
async def ask_question(req: QARequest) -> QAResponse:
    """Ask a question about a completed analysis."""
    # Validate job exists and analysis is available
    if req.job_id:
        from api.routes.pipeline import _jobs
        job = _jobs.get(req.job_id)
        if job is not None:
            from api.models import JobStatus
            status = job["status"]
            if isinstance(status, JobStatus):
                status = status.value
            if status != "completed":
                raise HTTPException(400, f"Job '{req.job_id}' 상태가 '{status}'입니다. 완료된 작업만 Q&A 가능합니다.")

    session = _get_or_create_session(req.job_id)

    answer = session.ask(req.question)

    # Persist session after each turn
    session_dir = _qa_session_dir(req.job_id)
    session.save_session(session_dir / f"{req.job_id}.json")

    # Extract follow-ups (already appended by qa_session)
    follow_ups = []
    if "**추가로 물어볼 수 있는 질문:**" in answer:
        parts = answer.split("**추가로 물어볼 수 있는 질문:**")
        answer = parts[0].strip()
        if len(parts) > 1:
            for line in parts[1].strip().split("\n"):
                line = line.strip().lstrip("- ")
                if line:
                    follow_ups.append(line)

    return QAResponse(
        answer=answer,
        follow_ups=follow_ups,
        context={"job_id": req.job_id, "turns": len(session.conversation_history) // 2},
    )


@router.post("/qa/reset")
async def reset_session(job_id: str = ""):
    """Reset a Q&A session."""
    if job_id in _sessions:
        _sessions[job_id].reset()
        del _sessions[job_id]
    return {"status": "ok"}


_JOBS_DIR = Path("data/jobs")


def _job_analysis_dir(job_id: str) -> Path:
    """Return the analysis directory for a job, or the global fallback."""
    job_dir = _JOBS_DIR / job_id / "pipeline" / "analysis"
    if job_dir.exists():
        return job_dir
    return Path("data/analysis")


def _qa_session_dir(job_id: str) -> Path:
    """Return the QA session directory for a job."""
    d = _JOBS_DIR / job_id / "pipeline" / "qa_sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_or_create_session(job_id: str):
    if job_id not in _sessions:
        from comad_eye.graph.neo4j_client import Neo4jClient
        from comad_eye.narration.qa_session import QASession
        from comad_eye.llm_client import LLMClient

        settings = load_settings()
        client = Neo4jClient(settings=settings.neo4j)
        llm = LLMClient(settings=settings.llm)
        analysis_dir = _job_analysis_dir(job_id)
        session_dir = _qa_session_dir(job_id)
        session = QASession(graph=client, llm=llm, analysis_dir=analysis_dir)
        session.load_session(session_dir / f"{job_id}.json")
        _sessions[job_id] = session

    return _sessions[job_id]
