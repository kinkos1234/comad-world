"""ComadEye FastAPI Server — wraps existing CLI pipeline as HTTP API."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI

logger = logging.getLogger("comadeye")
from fastapi.middleware.cors import CORSMiddleware

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.routes import analysis, graph, pipeline, qa, report  # noqa: E402


def _get_allowed_origins() -> list[str]:
    """Return allowed CORS origins from env, with a safe local default."""
    raw = os.getenv("CORS_ALLOW_ORIGINS") or os.getenv("COMADEYE_CORS_ALLOW_ORIGINS")
    if raw is None:
        return ["http://localhost:3000"]

    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or ["http://localhost:3000"]

app = FastAPI(
    title="ComadEye API",
    description="Ontology-Native Prediction Simulation Engine",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi import Request
from fastapi.responses import JSONResponse


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return standardized error response."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "code": "INTERNAL_ERROR",
            "detail": str(exc),
        },
    )


app.include_router(pipeline.router, prefix="/api", tags=["pipeline"])
app.include_router(analysis.router, prefix="/api", tags=["analysis"])
app.include_router(graph.router, prefix="/api", tags=["graph"])
app.include_router(qa.router, prefix="/api", tags=["qa"])
app.include_router(report.router, prefix="/api", tags=["report"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "comadeye"}


@app.get("/api/system-status")
async def system_status():
    """Check Neo4j and Ollama connectivity + device spec analysis."""
    from api.models import (
        DeviceInfoResponse,
        ModelRecommendationResponse,
        SystemStatus,
    )

    status = SystemStatus()

    # Device spec detection
    try:
        from comad_eye.device import detect_device
        device = detect_device()
        status.device = DeviceInfoResponse(
            total_ram_gb=device.total_ram_gb,
            cpu_cores=device.cpu_cores,
            gpu_type=device.gpu_type,
            os_name=device.os_name,
            arch=device.arch,
        )
    except Exception as e:
        logger.warning("Device detection failed: %s", e)
        device = None

    # Neo4j check
    neo4j_error = None
    try:
        from comad_eye.config import load_settings
        settings = load_settings()
        from comad_eye.graph.neo4j_client import Neo4jClient
        client = Neo4jClient(settings=settings.neo4j)
        client.query("RETURN 1")
        client.close()
        status.neo4j = True
    except Exception as e:
        neo4j_error = str(e)
        logger.warning("Neo4j health check failed: %s", e)

    # Ollama check + available models + fitness evaluation
    ollama_error = None
    try:
        import httpx
        from comad_eye.config import load_settings
        settings = load_settings()
        base = settings.llm.base_url.replace("/v1", "")
        resp = httpx.get(f"{base}/api/tags", timeout=3)
        if resp.status_code == 200:
            status.ollama = True
            models_data = resp.json().get("models", [])
            status.available_models = [m["name"] for m in models_data]
            is_auto = settings.llm.model == "auto"
            if not is_auto and settings.llm.model in status.available_models:
                status.llm_model = settings.llm.model
            elif status.available_models:
                status.llm_model = status.available_models[0]
            else:
                status.llm_model = settings.llm.model

            # Model fitness evaluation
            if device and status.available_models:
                from comad_eye.device import evaluate_all_models
                recs = evaluate_all_models(
                    device=device,
                    base_url=base,
                    model_names=status.available_models,
                )
                status.model_recommendations = [
                    ModelRecommendationResponse(
                        name=r.name,
                        size_gb=r.size_gb,
                        parameter_size=r.parameter_size,
                        fitness=r.fitness,
                        reason=r.reason,
                    )
                    for r in recs
                ]
        else:
            ollama_error = f"HTTP {resp.status_code}"
            logger.warning("Ollama returned status %d", resp.status_code)
    except Exception as e:
        ollama_error = str(e)
        logger.warning("Ollama health check failed: %s", e)

    # Include error details in response for diagnostics
    result = status.model_dump() if hasattr(status, "model_dump") else status.__dict__
    if neo4j_error:
        result["neo4j_error"] = neo4j_error
    if ollama_error:
        result["ollama_error"] = ollama_error
    return result
