"""Integration tests for API routes — uses FastAPI TestClient."""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi", reason="fastapi not installed")
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the ComadEye API."""
    from api.server import app
    return TestClient(app)


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "comadeye"


class TestAnalysisEndpoints:
    def test_lens_catalog(self, client):
        resp = client.get("/api/analysis/lenses")
        assert resp.status_code == 200
        data = resp.json()
        assert "lenses" in data
        assert "default_ids" in data
        assert isinstance(data["lenses"], list)
        assert len(data["lenses"]) > 0

    def test_lens_has_required_fields(self, client):
        resp = client.get("/api/analysis/lenses")
        data = resp.json()
        for lens in data["lenses"]:
            assert "id" in lens
            assert "name_ko" in lens
            assert "thinker" in lens

    def test_unknown_space_404(self, client):
        resp = client.get("/api/analysis/nonexistent")
        assert resp.status_code == 404

    def test_valid_space_names(self, client):
        """Valid space names should return 404 (no data) not 422 (validation error)."""
        for space in ["hierarchy", "temporal", "recursive", "structural", "causal", "cross_space"]:
            resp = client.get(f"/api/analysis/{space}")
            # 404 = no data file (expected in test), not 422 (bad route)
            assert resp.status_code in (200, 404), f"Unexpected status for {space}: {resp.status_code}"


class TestPipelineEndpoints:
    def test_list_jobs(self, client):
        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_nonexistent_job(self, client):
        resp = client.get("/api/jobs/nonexistent123")
        assert resp.status_code == 200  # returns error dict, not 404
        data = resp.json()
        assert "error" in data

    def test_delete_nonexistent_job(self, client):
        resp = client.delete("/api/jobs/nonexistent123")
        data = resp.json()
        assert "error" in data

    def test_preflight_valid(self, client):
        resp = client.post("/api/preflight", json={
            "seed_text": "This is a test seed text for preflight analysis.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "chars" in data
        assert "estimated_tokens" in data
        assert "risk_level" in data
        assert data["chars"] > 0

    def test_preflight_empty_text(self, client):
        resp = client.post("/api/preflight", json={
            "seed_text": "",
        })
        assert resp.status_code == 422  # Pydantic validation error


class TestErrorHandling:
    def test_404_route(self, client):
        resp = client.get("/api/nonexistent")
        assert resp.status_code in (404, 405)

    def test_global_exception_handler(self, client):
        """Verify the global exception handler catches unhandled errors gracefully."""
        # The system-status endpoint may fail if Neo4j/Ollama aren't running,
        # but it should return a valid JSON response, not crash
        resp = client.get("/api/system-status")
        assert resp.status_code == 200  # Always returns status, even if services are down
        data = resp.json()
        assert "neo4j" in data
        assert "ollama" in data
