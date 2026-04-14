"""Pipeline routes — run simulation and stream progress via SSE."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse

from api.models import (
    JobResponse,
    JobStatus,
    PipelineStage,
    PreflightRequest,
    PreflightResponse,
    RunPipelineRequest,
    StageUpdate,
)

router = APIRouter()
logger = logging.getLogger("comadeye")

# --- Job persistence ---
_JOBS_DIR = Path("data/jobs")
_JOBS_DIR.mkdir(parents=True, exist_ok=True)

# In-memory job store, loaded from disk on startup
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_stages_lock = threading.Lock()


def _job_data_dir(job_id: str) -> Path:
    """Return a job-scoped data directory: data/jobs/<job_id>/pipeline/."""
    d = _JOBS_DIR / job_id / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _job_path(job_id: str) -> Path:
    return _JOBS_DIR / f"{job_id}.json"


def _save_job(job_id: str) -> None:
    """Persist a job to disk as JSON."""
    job = _jobs.get(job_id)
    if not job:
        return
    serializable = {
        "job_id": job_id,
        "status": job["status"].value if isinstance(job["status"], JobStatus) else job["status"],
        "stages": job["stages"],
        "result": job.get("result"),
        "error": job.get("error"),
        "seed_text": job.get("seed_text", ""),
        "analysis_prompt": job.get("analysis_prompt"),
        "model_override": job.get("model_override"),
        "lenses": job.get("lenses"),
        "settings_override": job.get("settings_override", {}),
        "created_at": job.get("created_at", ""),
    }
    _job_path(job_id).write_text(
        json.dumps(serializable, ensure_ascii=False, default=str, indent=2),
        encoding="utf-8",
    )


def _load_jobs() -> None:
    """Load all persisted jobs from disk into memory."""
    for p in _JOBS_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            job_id = data["job_id"]
            # Convert status string back to enum
            status_str = data.get("status", "completed")
            # Running/pending jobs from a previous server session are treated as failed
            if status_str in ("running", "pending"):
                status_str = "failed"
                data["error"] = data.get("error") or "서버 재시작으로 중단됨"
            _jobs[job_id] = {
                "status": JobStatus(status_str),
                "stages": data.get("stages", []),
                "result": data.get("result"),
                "error": data.get("error"),
                "seed_text": data.get("seed_text", ""),
                "analysis_prompt": data.get("analysis_prompt"),
                "model_override": data.get("model_override"),
                "lenses": data.get("lenses"),
                "settings_override": data.get("settings_override", {}),
                "created_at": data.get("created_at", ""),
            }
        except Exception:
            logger.warning("Failed to load job file: %s", p)


# Load persisted jobs on module import
_load_jobs()
logger.info("Loaded %d persisted jobs from %s", len(_jobs), _JOBS_DIR)


@router.post("/run")
async def run_pipeline(
    req: RunPipelineRequest,
    background_tasks: BackgroundTasks,
) -> JobResponse:
    """Start the full pipeline asynchronously."""
    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[job_id] = {
            "status": JobStatus.PENDING,
            "stages": [],
            "result": None,
            "error": None,
            "seed_text": req.seed_text,
            "analysis_prompt": req.analysis_prompt,
            "model_override": req.model,
            "lenses": req.lenses,
            "settings_override": {
                "max_rounds": req.max_rounds,
                "propagation_decay": req.propagation_decay,
                "propagation_max_hops": req.max_hops,
                "volatility_decay": req.volatility_decay,
                "convergence_threshold": req.convergence_threshold,
            },
            "resume_from_cache": req.resume_from_cache,
            "created_at": datetime.now().isoformat(),
        }

    # Job-scoped data directory
    data_dir = _job_data_dir(job_id)

    # 캐시 재사용 비활성화 시 기존 추출 캐시 삭제
    if not req.resume_from_cache:
        cache_dir = data_dir / "extraction" / "chunk_results"
        if cache_dir.exists():
            import shutil
            shutil.rmtree(cache_dir, ignore_errors=True)
            logger.info("추출 캐시 삭제됨 (resume_from_cache=false)")

    _save_job(job_id)
    background_tasks.add_task(_execute_pipeline, job_id)
    return JobResponse(job_id=job_id, status=JobStatus.PENDING)


@router.get("/status/{job_id}")
async def stream_status(job_id: str):
    """Stream pipeline progress as Server-Sent Events."""
    if job_id not in _jobs:
        return {"error": "Job not found"}

    async def event_stream():
        seen = 0
        while True:
            job = _jobs.get(job_id)
            if not job:
                break

            # Snapshot stages under lock to avoid partial reads
            with _stages_lock:
                stages_snapshot = list(job["stages"])

            # Send new stage updates
            while seen < len(stages_snapshot):
                update = stages_snapshot[seen]
                yield f"data: {json.dumps(update, ensure_ascii=False, default=str)}\n\n"
                seen += 1

            if job["status"] in (JobStatus.COMPLETED, JobStatus.FAILED):
                final = {
                    "stage": "done",
                    "status": job["status"].value,
                    "data": job.get("result") or {},
                    "error": job.get("error"),
                }
                yield f"data: {json.dumps(final, ensure_ascii=False, default=str)}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/jobs")
async def list_jobs():
    """List all jobs with their status."""
    jobs = [
        {
            "job_id": jid,
            "status": job["status"].value if isinstance(job["status"], JobStatus) else job["status"],
            "seed_text": (job.get("seed_text", "") or "")[:100],
            "created_at": job.get("created_at", ""),
        }
        for jid, job in _jobs.items()
    ]
    # Sort by created_at descending (newest first)
    jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
    return jobs


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Get job details."""
    job = _jobs.get(job_id)
    if not job:
        return {"error": "Job not found"}
    return {
        "job_id": job_id,
        "status": job["status"].value if isinstance(job["status"], JobStatus) else job["status"],
        "seed_text": job.get("seed_text", ""),
        "stages": job["stages"],
        "result": job.get("result"),
        "error": job.get("error"),
    }


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job from memory and disk."""
    with _jobs_lock:
        if job_id not in _jobs:
            return {"error": "Job not found"}
        # Don't allow deleting running jobs
        job = _jobs[job_id]
        status = job["status"].value if isinstance(job["status"], JobStatus) else job["status"]
        if status == "running":
            return {"error": "Cannot delete a running job"}
        # Remove from memory
        del _jobs[job_id]
    # Remove from disk
    path = _job_path(job_id)
    if path.exists():
        path.unlink()
    # Remove job data directory
    job_data = _JOBS_DIR / job_id / "pipeline"
    if job_data.exists():
        import shutil
        shutil.rmtree(job_data, ignore_errors=True)
    return {"deleted": job_id}


def _push_stage(job_id: str, stage: PipelineStage, status: JobStatus, message: str = "", data: dict | None = None):
    update = StageUpdate(stage=stage, status=status, message=message, data=data or {})
    with _stages_lock:
        _jobs[job_id]["stages"].append(update.model_dump())
    _save_job(job_id)


def _execute_pipeline(job_id: str):
    """Run the full pipeline synchronously (in background thread)."""
    from comad_eye.config import load_settings

    job = _jobs[job_id]
    job["status"] = JobStatus.RUNNING
    _save_job(job_id)
    settings = load_settings()

    # Apply model override or auto-detect
    model_override = job.get("model_override")
    if model_override:
        settings.llm.model = model_override
    else:
        # Auto-detect: check if configured model is available in Ollama
        try:
            import httpx
            base = settings.llm.base_url.replace("/v1", "")
            resp = httpx.get(f"{base}/api/tags", timeout=5)
            if resp.status_code == 200:
                available = [m["name"] for m in resp.json().get("models", [])]
                is_auto = settings.llm.model == "auto"
                if available and (is_auto or settings.llm.model not in available):
                    selected = available[0]
                    logger.info(
                        "Model auto-detect: configured='%s', available=%s, selected='%s'",
                        settings.llm.model, available, selected,
                    )
                    settings.llm.model = selected
        except Exception:
            pass  # Ollama unreachable — proceed with configured model

    # qwen3 thinking 모델 경고 및 설정 조정
    if "qwen3" in settings.llm.model.lower():
        logger.warning(
            "qwen3 계열 thinking 모델 감지 (%s). "
            "JSON 구조화 작업에서 속도가 매우 느릴 수 있습니다. "
            "llama3.1:8b 사용을 권장합니다.",
            settings.llm.model,
        )
        # thinking 예산 확보: max_tokens 상향
        if settings.llm.max_tokens < 2048:
            settings.llm.max_tokens = 2048

    # Apply simulation overrides
    for key, val in job["settings_override"].items():
        if hasattr(settings.simulation, key):
            setattr(settings.simulation, key, val)

    seed_text = job["seed_text"]
    analysis_prompt = job.get("analysis_prompt")

    try:
        # LLM usage accumulator
        llm_usage = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "tokens_total": 0}

        def _merge_usage(stats: dict[str, int]) -> None:
            for k in llm_usage:
                llm_usage[k] += stats.get(k, 0)

        # Stage 1: Ingestion
        _push_stage(job_id, PipelineStage.INGESTION, JobStatus.RUNNING, "시드 데이터 처리 중...")

        def _ingestion_progress(completed: int, total: int, failed: int, retrying: int, message: str) -> None:
            _push_stage(
                job_id, PipelineStage.INGESTION, JobStatus.RUNNING, message,
                {"chunk_completed": completed, "chunk_total": total, "chunk_failed": failed, "chunk_retrying": retrying},
            )

        # Job-scoped data directory
        data_dir = _job_data_dir(job_id)

        from comad_eye.pipeline.orchestrator import run_ingestion
        chunks, ontology, ingestion_usage = run_ingestion(
            seed_text, settings, on_progress=_ingestion_progress, data_dir=data_dir,
        )
        _merge_usage(ingestion_usage)
        _push_stage(job_id, PipelineStage.INGESTION, JobStatus.COMPLETED,
                    f"엔티티 {len(ontology.entities)}개, 관계 {len(ontology.relationships)}개 추출",
                    {"entities": len(ontology.entities), "links": len(ontology.relationships)})

        # Stage 2: Graph
        _push_stage(job_id, PipelineStage.GRAPH, JobStatus.RUNNING, "Neo4j 그래프 로딩...")
        from comad_eye.pipeline.orchestrator import run_graph_loading
        client = run_graph_loading(ontology, settings)
        _push_stage(job_id, PipelineStage.GRAPH, JobStatus.COMPLETED, "그래프 로딩 완료")

        # Stage 3: Community
        _push_stage(job_id, PipelineStage.COMMUNITY, JobStatus.RUNNING, "커뮤니티 탐지 중...")
        from comad_eye.pipeline.orchestrator import run_community_detection
        community_usage = run_community_detection(client, settings)
        _merge_usage(community_usage)
        _push_stage(job_id, PipelineStage.COMMUNITY, JobStatus.COMPLETED, "커뮤니티 탐지 완료")

        # Stage 4: Simulation
        _push_stage(job_id, PipelineStage.SIMULATION, JobStatus.RUNNING, "시뮬레이션 실행 중...")
        from comad_eye.pipeline.orchestrator import run_simulation
        sim_result = run_simulation(client, ontology, settings, data_dir=data_dir)
        _push_stage(job_id, PipelineStage.SIMULATION, JobStatus.COMPLETED,
                    f"라운드 {sim_result['total_rounds']}회 완료",
                    sim_result)

        # Stage 5: Analysis + Lens Deep Filters
        selected_lenses = job.get("lenses")
        lens_label = f" + 렌즈 {len(selected_lenses)}개" if selected_lenses else " + 렌즈 자동 선별"
        _push_stage(job_id, PipelineStage.ANALYSIS, JobStatus.RUNNING,
                    f"6개 분석공간{lens_label} 실행 중...")
        from comad_eye.pipeline.orchestrator import run_analysis
        aggregated = run_analysis(
            client, settings,
            lenses=selected_lenses,
            seed_text=seed_text,
            analysis_prompt=analysis_prompt,
            settings_override=job.get("settings_override"),
            data_dir=data_dir,
        )
        n_findings = len(aggregated.get("key_findings", []))
        n_lens = sum(len(v) for v in aggregated.get("lens_insights", {}).values())
        lens_msg = f", 렌즈 인사이트 {n_lens}개" if n_lens else ""
        _push_stage(job_id, PipelineStage.ANALYSIS, JobStatus.COMPLETED,
                    f"분석 완료 — {n_findings}개 핵심 발견{lens_msg}",
                    {"key_findings_count": n_findings, "lens_insights_count": n_lens})

        # Stage 6: Report
        _push_stage(job_id, PipelineStage.REPORT, JobStatus.RUNNING, "리포트 생성 중...")
        from comad_eye.pipeline.orchestrator import run_report
        report_dir = data_dir / "reports"
        report_path, report_usage = run_report(seed_text, sim_result, report_dir, settings, analysis_prompt=analysis_prompt, data_dir=data_dir)
        _merge_usage(report_usage)
        _push_stage(job_id, PipelineStage.REPORT, JobStatus.COMPLETED,
                    f"리포트 생성 완료: {report_path}")

        client.close()

        job["status"] = JobStatus.COMPLETED
        job["result"] = {
            **sim_result,
            "key_findings_count": n_findings,
            "report_path": str(report_path),
            "llm_usage": llm_usage,
        }
        _save_job(job_id)

    except Exception as e:
        logger.exception("Pipeline failed for job %s", job_id)
        job["status"] = JobStatus.FAILED
        job["error"] = str(e)
        _save_job(job_id)


@router.post("/retry/{job_id}")
async def retry_job(
    job_id: str,
    background_tasks: BackgroundTasks,
) -> JobResponse:
    """실패한 작업을 캐시 재사용하여 재실행한다."""
    old_job = _jobs.get(job_id)
    if not old_job:
        return JobResponse(job_id=job_id, status=JobStatus.FAILED)

    new_job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[new_job_id] = {
            "status": JobStatus.PENDING,
            "stages": [],
            "result": None,
            "error": None,
            "seed_text": old_job.get("seed_text", ""),
            "analysis_prompt": old_job.get("analysis_prompt"),
            "model_override": old_job.get("model_override"),
            "lenses": old_job.get("lenses"),
            "settings_override": old_job.get("settings_override", {}),
            "resume_from_cache": True,
            "created_at": datetime.now().isoformat(),
        }
    _save_job(new_job_id)
    background_tasks.add_task(_execute_pipeline, new_job_id)
    return JobResponse(job_id=new_job_id, status=JobStatus.PENDING)


@router.post("/preflight", response_model=PreflightResponse)
def preflight(req: PreflightRequest):
    """시드 텍스트 사전 진단 — 토큰 추정, 위험도, 예상 배치 수."""
    from comad_eye.preflight import run_preflight

    result = run_preflight(
        text=req.seed_text,
        chunk_size=req.chunk_size,
        chunk_overlap=req.chunk_overlap,
        batch_size=req.batch_size,
    )
    return PreflightResponse(
        chars=result.chars,
        estimated_tokens=result.estimated_tokens,
        sentences=result.sentences,
        risk_level=result.risk_level,
        recommended_batch_size=result.recommended_batch_size,
        expected_batches=result.expected_batches,
        expected_llm_calls=result.expected_llm_calls,
        warnings=result.warnings,
    )
