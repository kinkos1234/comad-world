"""Analysis routes — serve analysis space results."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from utils.cache import _SENTINEL, analysis_file_cache

router = APIRouter()

_GLOBAL_ANALYSIS_DIR = Path("data/analysis")
_JOBS_DIR = Path("data/jobs")


def _analysis_dir(job_id: str | None) -> Path:
    """Return the analysis directory for a job, or the global fallback."""
    if job_id:
        d = _JOBS_DIR / job_id / "pipeline" / "analysis"
        if d.exists():
            return d
    return _GLOBAL_ANALYSIS_DIR


@router.get("/analysis/lenses")
async def get_lens_catalog():
    """Return the catalog of available analysis lenses."""
    from analysis.lenses import DEFAULT_LENS_IDS, LENS_CATALOG

    return {
        "lenses": [
            {
                "id": lens.id,
                "name_ko": lens.name_ko,
                "name_en": lens.name_en,
                "thinker": lens.thinker,
                "framework": lens.framework,
                "default_enabled": lens.default_enabled,
            }
            for lens in LENS_CATALOG
        ],
        "default_ids": DEFAULT_LENS_IDS,
    }


@router.get("/analysis/lens-insights")
async def get_lens_insights(job_id: str | None = Query(None)):
    """Return lens deep filter insights."""
    return _load_or_404("lens_insights", job_id)


@router.get("/analysis/lens-cross")
async def get_lens_cross(job_id: str | None = Query(None)):
    """Return lens cross-synthesis insights."""
    return _load_or_404("lens_cross", job_id)


@router.get("/analysis/aggregated")
async def get_aggregated(job_id: str | None = Query(None)):
    """Return the aggregated analysis result."""
    return _load_or_404("aggregated", job_id)


@router.get("/analysis/{space}")
async def get_space(space: str, job_id: str | None = Query(None)):
    """Return a single analysis space result."""
    valid = ["hierarchy", "temporal", "recursive", "structural", "causal", "cross_space"]
    if space not in valid:
        raise HTTPException(404, f"Unknown space: {space}. Valid: {valid}")
    return _load_or_404(space, job_id)


def clear_analysis_cache() -> None:
    """Invalidate all cached analysis file reads.

    Call this after a new analysis job completes so that fresh results
    are served on the next request.
    """
    analysis_file_cache.clear()


def _load_or_404(name: str, job_id: str | None = None) -> dict:
    base = _analysis_dir(job_id)
    path = base / f"{name}.json"

    cache_key = str(path)
    cached = analysis_file_cache.get_or_sentinel(cache_key)
    if cached is not _SENTINEL:
        return cached  # type: ignore[return-value]

    if not path.exists():
        raise HTTPException(404, f"Analysis result not found: {name}")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise HTTPException(
            500,
            f"Analysis result '{name}' is corrupted (invalid JSON): {e}",
        )
    analysis_file_cache.set(cache_key, data)
    return data
