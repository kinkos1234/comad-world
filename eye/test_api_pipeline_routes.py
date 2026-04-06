"""Tests for api/routes/pipeline.py — pipeline, jobs, preflight endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import patch

import pytest

fastapi = pytest.importorskip("fastapi", reason="fastapi not installed")
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api.server import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_jobs():
    """Clean up the in-memory job store before and after each test."""
    from api.routes.pipeline import _jobs, _jobs_lock
    with _jobs_lock:
        _jobs.clear()
    yield
    with _jobs_lock:
        _jobs.clear()


def _seed_job(job_id, status="completed", seed_text="test text", error=None):
    """Helper to directly insert a job into the in-memory store."""
    from api.models import JobStatus
    from api.routes.pipeline import _jobs, _jobs_lock

    with _jobs_lock:
        _jobs[job_id] = {
            "status": JobStatus(status),
            "stages": [],
            "result": {"total_rounds": 5} if status == "completed" else None,
            "error": error,
            "seed_text": seed_text,
            "analysis_prompt": None,
            "model_override": None,
            "lenses": None,
            "settings_override": {},
            "created_at": datetime.now().isoformat(),
        }


# ---------------------------------------------------------------------------
# GET /api/jobs
# ---------------------------------------------------------------------------
class TestListJobs:
    def test_empty_jobs(self, client):
        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_lists_seeded_jobs(self, client):
        _seed_job("abc123", "completed", "hello world")
        _seed_job("def456", "failed", "another text", error="boom")

        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        ids = {j["job_id"] for j in data}
        assert ids == {"abc123", "def456"}

    def test_jobs_sorted_by_created_at_desc(self, client):
        _seed_job("old_job")
        _seed_job("new_job")

        # Manually set created_at to control sort order
        from api.routes.pipeline import _jobs
        _jobs["old_job"]["created_at"] = "2024-01-01T00:00:00"
        _jobs["new_job"]["created_at"] = "2024-12-01T00:00:00"

        resp = client.get("/api/jobs")
        data = resp.json()
        assert data[0]["job_id"] == "new_job"
        assert data[1]["job_id"] == "old_job"

    def test_seed_text_truncated_to_100_chars(self, client):
        long_text = "A" * 200
        _seed_job("longtext", seed_text=long_text)

        resp = client.get("/api/jobs")
        data = resp.json()
        assert len(data[0]["seed_text"]) == 100


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}
# ---------------------------------------------------------------------------
class TestGetJob:
    def test_existing_job(self, client):
        _seed_job("abc123", "completed", "test seed text")

        resp = client.get("/api/jobs/abc123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "abc123"
        assert data["status"] == "completed"
        assert data["seed_text"] == "test seed text"
        assert "stages" in data

    def test_nonexistent_job(self, client):
        resp = client.get("/api/jobs/nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data
        assert data["error"] == "Job not found"

    def test_failed_job_includes_error(self, client):
        _seed_job("failed_job", "failed", error="Pipeline exploded")

        resp = client.get("/api/jobs/failed_job")
        data = resp.json()
        assert data["status"] == "failed"
        assert data["error"] == "Pipeline exploded"


# ---------------------------------------------------------------------------
# DELETE /api/jobs/{job_id}
# ---------------------------------------------------------------------------
class TestDeleteJob:
    def test_delete_existing_completed_job(self, client, tmp_path):
        _seed_job("todelete", "completed")

        # Mock the disk path so we don't touch real filesystem
        with patch("api.routes.pipeline._job_path", return_value=tmp_path / "todelete.json"):
            with patch("api.routes.pipeline._JOBS_DIR", tmp_path):
                resp = client.delete("/api/jobs/todelete")
                assert resp.status_code == 200
                data = resp.json()
                assert data["deleted"] == "todelete"

        # Verify removed from memory
        from api.routes.pipeline import _jobs
        assert "todelete" not in _jobs

    def test_delete_nonexistent_job(self, client):
        resp = client.delete("/api/jobs/nonexistent")
        data = resp.json()
        assert "error" in data
        assert data["error"] == "Job not found"

    def test_delete_running_job_prevented(self, client):
        _seed_job("running_job", "running")

        resp = client.delete("/api/jobs/running_job")
        data = resp.json()
        assert "error" in data
        assert "running" in data["error"].lower()

    def test_delete_failed_job(self, client, tmp_path):
        _seed_job("failed_job", "failed")

        with patch("api.routes.pipeline._job_path", return_value=tmp_path / "failed.json"):
            with patch("api.routes.pipeline._JOBS_DIR", tmp_path):
                resp = client.delete("/api/jobs/failed_job")
                assert resp.status_code == 200
                assert resp.json()["deleted"] == "failed_job"


# ---------------------------------------------------------------------------
# POST /api/run
# ---------------------------------------------------------------------------
class TestRunPipeline:
    def test_run_creates_job(self, client, tmp_path):
        """Starting a pipeline should return a job_id with pending status."""
        with patch("api.routes.pipeline._job_data_dir", return_value=tmp_path / "pipeline"):
            with patch("api.routes.pipeline._save_job"):
                with patch("api.routes.pipeline._execute_pipeline"):
                    resp = client.post("/api/run", json={
                        "seed_text": "This is a sufficiently long seed text for testing.",
                    })
                    assert resp.status_code == 200
                    data = resp.json()
                    assert "job_id" in data
                    assert data["status"] == "pending"
                    assert len(data["job_id"]) == 12

    def test_run_with_all_parameters(self, client, tmp_path):
        with patch("api.routes.pipeline._job_data_dir", return_value=tmp_path / "pipeline"):
            with patch("api.routes.pipeline._save_job"):
                with patch("api.routes.pipeline._execute_pipeline"):
                    resp = client.post("/api/run", json={
                        "seed_text": "This is a sufficiently long seed text for testing.",
                        "analysis_prompt": "Focus on political dynamics",
                        "model": "llama3.1:8b",
                        "max_rounds": 20,
                        "propagation_decay": 0.5,
                        "max_hops": 5,
                        "volatility_decay": 0.05,
                        "convergence_threshold": 0.02,
                        "lenses": ["sun_tzu", "machiavelli"],
                        "resume_from_cache": False,
                    })
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["status"] == "pending"

    def test_run_with_short_text_rejected(self, client):
        """seed_text with min_length=10 should reject very short text."""
        resp = client.post("/api/run", json={"seed_text": "short"})
        assert resp.status_code == 422

    def test_run_with_empty_text_rejected(self, client):
        resp = client.post("/api/run", json={"seed_text": ""})
        assert resp.status_code == 422

    def test_run_invalid_max_rounds(self, client):
        resp = client.post("/api/run", json={
            "seed_text": "This is a sufficiently long seed text for testing.",
            "max_rounds": 0,  # ge=1
        })
        assert resp.status_code == 422

    def test_run_invalid_propagation_decay(self, client):
        resp = client.post("/api/run", json={
            "seed_text": "This is a sufficiently long seed text for testing.",
            "propagation_decay": 1.5,  # le=1.0
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/retry/{job_id}
# ---------------------------------------------------------------------------
class TestRetryJob:
    def test_retry_existing_failed_job(self, client, tmp_path):
        _seed_job("failed_job", "failed", "original seed text")

        with patch("api.routes.pipeline._job_data_dir", return_value=tmp_path / "pipeline"):
            with patch("api.routes.pipeline._save_job"):
                with patch("api.routes.pipeline._execute_pipeline"):
                    resp = client.post("/api/retry/failed_job")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert "job_id" in data
                    assert data["job_id"] != "failed_job"  # new job id
                    assert data["status"] == "pending"

    def test_retry_nonexistent_job(self, client):
        resp = client.post("/api/retry/nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"


# ---------------------------------------------------------------------------
# POST /api/preflight
# ---------------------------------------------------------------------------
class TestPreflight:
    def test_valid_preflight(self, client):
        resp = client.post("/api/preflight", json={
            "seed_text": "This is a test seed text for preflight analysis.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "chars" in data
        assert "estimated_tokens" in data
        assert "risk_level" in data
        assert "recommended_batch_size" in data
        assert "expected_batches" in data
        assert "expected_llm_calls" in data
        assert "warnings" in data
        assert data["chars"] > 0
        assert data["estimated_tokens"] > 0

    def test_preflight_with_custom_params(self, client):
        resp = client.post("/api/preflight", json={
            "seed_text": "A moderately long text for preflight with custom parameters.",
            "chunk_size": 200,
            "chunk_overlap": 50,
            "batch_size": 4,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["chars"] > 0

    def test_preflight_empty_text_rejected(self, client):
        resp = client.post("/api/preflight", json={"seed_text": ""})
        assert resp.status_code == 422

    def test_preflight_missing_text_rejected(self, client):
        resp = client.post("/api/preflight", json={})
        assert resp.status_code == 422

    def test_preflight_invalid_chunk_size(self, client):
        resp = client.post("/api/preflight", json={
            "seed_text": "Valid text here.",
            "chunk_size": 10,  # ge=100
        })
        assert resp.status_code == 422

    def test_preflight_invalid_batch_size(self, client):
        resp = client.post("/api/preflight", json={
            "seed_text": "Valid text here.",
            "batch_size": 0,  # ge=1
        })
        assert resp.status_code == 422

    def test_preflight_long_text(self, client):
        long_text = "This is a sentence. " * 500
        resp = client.post("/api/preflight", json={"seed_text": long_text})
        assert resp.status_code == 200
        data = resp.json()
        assert data["chars"] > 1000
        assert data["sentences"] > 0

    def test_preflight_response_warnings_is_list(self, client):
        resp = client.post("/api/preflight", json={
            "seed_text": "Short but valid text here.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["warnings"], list)


# ---------------------------------------------------------------------------
# GET /api/status/{job_id} (SSE stream)
# ---------------------------------------------------------------------------
class TestStreamStatus:
    def test_nonexistent_job_returns_error(self, client):
        resp = client.get("/api/status/nonexistent")
        # The endpoint returns a JSON dict for nonexistent, not SSE
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data

    def test_completed_job_streams_done_event(self, client):
        _seed_job("completed_job", "completed")

        resp = client.get("/api/status/completed_job")
        assert resp.status_code == 200
        # SSE responses come as text/event-stream
        assert resp.headers.get("content-type", "").startswith("text/event-stream")
        # The stream should contain a "done" event
        body = resp.text
        assert "done" in body

    def test_failed_job_streams_done_with_error(self, client):
        _seed_job("fail_job", "failed", error="Something broke")

        resp = client.get("/api/status/fail_job")
        assert resp.status_code == 200
        body = resp.text
        assert "done" in body
        assert "Something broke" in body


# ---------------------------------------------------------------------------
# Job persistence helpers
# ---------------------------------------------------------------------------
class TestJobPersistence:
    def test_save_job_writes_to_disk(self, tmp_path):
        from api.models import JobStatus
        from api.routes.pipeline import _jobs, _jobs_lock, _save_job

        job_id = "test_persist"
        with _jobs_lock:
            _jobs[job_id] = {
                "status": JobStatus.COMPLETED,
                "stages": [],
                "result": {"total_rounds": 5},
                "error": None,
                "seed_text": "test text",
                "analysis_prompt": None,
                "model_override": None,
                "lenses": None,
                "settings_override": {},
                "created_at": "2024-01-01T00:00:00",
            }

        with patch("api.routes.pipeline._job_path", return_value=tmp_path / f"{job_id}.json"):
            _save_job(job_id)
            saved = json.loads((tmp_path / f"{job_id}.json").read_text(encoding="utf-8"))
            assert saved["job_id"] == job_id
            assert saved["status"] == "completed"
            assert saved["seed_text"] == "test text"

    def test_save_job_noop_for_unknown_job(self, tmp_path):
        from api.routes.pipeline import _save_job
        with patch("api.routes.pipeline._job_path", return_value=tmp_path / "unknown.json"):
            _save_job("unknown")
            assert not (tmp_path / "unknown.json").exists()

    def test_load_jobs_from_disk(self, tmp_path):
        """Verify _load_jobs can restore persisted jobs."""
        from api.routes.pipeline import _jobs, _jobs_lock, _load_jobs

        # Write a job file to disk
        job_data = {
            "job_id": "loaded_job",
            "status": "completed",
            "stages": [],
            "result": {"total_rounds": 3},
            "error": None,
            "seed_text": "loaded text",
            "analysis_prompt": None,
            "model_override": None,
            "lenses": None,
            "settings_override": {},
            "created_at": "2024-06-15T12:00:00",
        }
        (tmp_path / "loaded_job.json").write_text(
            json.dumps(job_data), encoding="utf-8"
        )

        with _jobs_lock:
            _jobs.clear()
        with patch("api.routes.pipeline._JOBS_DIR", tmp_path):
            _load_jobs()
            assert "loaded_job" in _jobs
            from api.models import JobStatus
            assert _jobs["loaded_job"]["status"] == JobStatus.COMPLETED

    def test_load_jobs_marks_running_as_failed(self, tmp_path):
        """Running jobs from previous session should be treated as failed."""
        from api.routes.pipeline import _jobs, _jobs_lock, _load_jobs

        job_data = {
            "job_id": "stale_running",
            "status": "running",
            "stages": [],
            "seed_text": "stale",
            "created_at": "2024-01-01T00:00:00",
        }
        (tmp_path / "stale_running.json").write_text(
            json.dumps(job_data), encoding="utf-8"
        )

        with _jobs_lock:
            _jobs.clear()
        with patch("api.routes.pipeline._JOBS_DIR", tmp_path):
            _load_jobs()
            from api.models import JobStatus
            assert _jobs["stale_running"]["status"] == JobStatus.FAILED
            assert "재시작" in (_jobs["stale_running"].get("error") or "")

    def test_load_jobs_skips_corrupt_file(self, tmp_path):
        """Corrupt JSON files should be skipped without crashing."""
        from api.routes.pipeline import _jobs, _jobs_lock, _load_jobs

        (tmp_path / "corrupt.json").write_text("NOT JSON", encoding="utf-8")

        with _jobs_lock:
            _jobs.clear()
        with patch("api.routes.pipeline._JOBS_DIR", tmp_path):
            _load_jobs()  # Should not raise
            assert len(_jobs) == 0


# ---------------------------------------------------------------------------
# Request model validation
# ---------------------------------------------------------------------------
class TestRequestValidation:
    def test_run_pipeline_request_defaults(self, client, tmp_path):
        """Verify default values are applied when optional fields are omitted."""
        with patch("api.routes.pipeline._job_data_dir", return_value=tmp_path / "pipeline"):
            with patch("api.routes.pipeline._save_job"):
                with patch("api.routes.pipeline._execute_pipeline"):
                    resp = client.post("/api/run", json={
                        "seed_text": "This is a sufficiently long seed text for testing purposes.",
                    })
                    assert resp.status_code == 200

        from api.routes.pipeline import _jobs
        job_id = list(_jobs.keys())[0]
        job = _jobs[job_id]
        assert job["settings_override"]["max_rounds"] == 10
        assert job["settings_override"]["propagation_decay"] == 0.6

    def test_preflight_request_defaults(self, client):
        resp = client.post("/api/preflight", json={
            "seed_text": "A test seed text for default parameters.",
        })
        assert resp.status_code == 200
