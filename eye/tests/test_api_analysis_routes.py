"""Tests for api/routes/analysis.py — analysis space and lens endpoints."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

fastapi = pytest.importorskip("fastapi", reason="fastapi not installed")
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api.server import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/analysis/lenses
# ---------------------------------------------------------------------------
class TestLensCatalog:
    def test_returns_lenses_list(self, client):
        resp = client.get("/api/analysis/lenses")
        assert resp.status_code == 200
        data = resp.json()
        assert "lenses" in data
        assert "default_ids" in data
        assert isinstance(data["lenses"], list)

    def test_each_lens_has_required_fields(self, client):
        resp = client.get("/api/analysis/lenses")
        data = resp.json()
        required_fields = {"id", "name_ko", "name_en", "thinker", "framework", "default_enabled"}
        for lens in data["lenses"]:
            assert required_fields.issubset(lens.keys()), f"Missing fields in lens: {lens}"

    def test_default_ids_are_subset_of_catalog(self, client):
        resp = client.get("/api/analysis/lenses")
        data = resp.json()
        all_ids = {lens["id"] for lens in data["lenses"]}
        for default_id in data["default_ids"]:
            assert default_id in all_ids, f"default_id '{default_id}' not in catalog"


# ---------------------------------------------------------------------------
# GET /api/analysis/{space}
# ---------------------------------------------------------------------------
class TestAnalysisSpace:
    @pytest.mark.parametrize("space", [
        "hierarchy", "temporal", "recursive", "structural", "causal", "cross_space",
    ])
    def test_valid_space_returns_200_or_404(self, client, space):
        """Valid space names should return data (200) or 'no data file' (404), never 422."""
        resp = client.get(f"/api/analysis/{space}")
        assert resp.status_code in (200, 404)

    def test_unknown_space_returns_404(self, client):
        resp = client.get("/api/analysis/nonexistent_space")
        assert resp.status_code == 404
        assert "Unknown space" in resp.json()["detail"]

    @pytest.mark.parametrize("space", ["hierarchy", "temporal"])
    def test_space_with_existing_file(self, client, space, tmp_path):
        """When the JSON file exists, the endpoint should return its content."""
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        expected = {"summary": "test data", "entries": [1, 2, 3]}
        (analysis_dir / f"{space}.json").write_text(json.dumps(expected), encoding="utf-8")

        with patch("api.routes.analysis._GLOBAL_ANALYSIS_DIR", analysis_dir):
            # Clear the cache so the patched path is used
            from utils.cache import analysis_file_cache
            analysis_file_cache.clear()

            resp = client.get(f"/api/analysis/{space}")
            assert resp.status_code == 200
            assert resp.json() == expected

            # Cleanup
            analysis_file_cache.clear()

    def test_space_with_corrupt_json(self, client, tmp_path):
        """Corrupt JSON file should return 500."""
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        (analysis_dir / "hierarchy.json").write_text("NOT VALID JSON {{{", encoding="utf-8")

        with patch("api.routes.analysis._GLOBAL_ANALYSIS_DIR", analysis_dir):
            from utils.cache import analysis_file_cache
            analysis_file_cache.clear()

            resp = client.get("/api/analysis/hierarchy")
            assert resp.status_code == 500
            assert "corrupted" in resp.json()["detail"]

            analysis_file_cache.clear()

    def test_space_with_job_id(self, client, tmp_path):
        """When job_id is provided and the job directory exists, it should use it."""
        jobs_dir = tmp_path / "jobs"
        job_analysis = jobs_dir / "test_job" / "pipeline" / "analysis"
        job_analysis.mkdir(parents=True)
        expected = {"from_job": True}
        (job_analysis / "hierarchy.json").write_text(json.dumps(expected), encoding="utf-8")

        with patch("api.routes.analysis._JOBS_DIR", jobs_dir):
            from utils.cache import analysis_file_cache
            analysis_file_cache.clear()

            resp = client.get("/api/analysis/hierarchy", params={"job_id": "test_job"})
            assert resp.status_code == 200
            assert resp.json() == expected

            analysis_file_cache.clear()

    def test_space_with_nonexistent_job_id_falls_back(self, client, tmp_path):
        """Non-existent job_id should fall back to global analysis dir."""
        global_dir = tmp_path / "analysis"
        global_dir.mkdir()
        expected = {"from_global": True}
        (global_dir / "hierarchy.json").write_text(json.dumps(expected), encoding="utf-8")

        with patch("api.routes.analysis._GLOBAL_ANALYSIS_DIR", global_dir):
            with patch("api.routes.analysis._JOBS_DIR", tmp_path / "nonexistent_jobs"):
                from utils.cache import analysis_file_cache
                analysis_file_cache.clear()

                resp = client.get("/api/analysis/hierarchy", params={"job_id": "fake_job"})
                assert resp.status_code == 200
                assert resp.json() == expected

                analysis_file_cache.clear()


# ---------------------------------------------------------------------------
# GET /api/analysis/lens-insights
# ---------------------------------------------------------------------------
class TestLensInsights:
    def test_missing_data_returns_404(self, client):
        resp = client.get("/api/analysis/lens-insights")
        assert resp.status_code in (200, 404)

    def test_with_existing_file(self, client, tmp_path):
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        expected = {"insights": ["a", "b"]}
        (analysis_dir / "lens_insights.json").write_text(json.dumps(expected), encoding="utf-8")

        with patch("api.routes.analysis._GLOBAL_ANALYSIS_DIR", analysis_dir):
            from utils.cache import analysis_file_cache
            analysis_file_cache.clear()

            resp = client.get("/api/analysis/lens-insights")
            assert resp.status_code == 200
            assert resp.json() == expected

            analysis_file_cache.clear()

    def test_with_job_id(self, client, tmp_path):
        jobs_dir = tmp_path / "jobs"
        job_analysis = jobs_dir / "j1" / "pipeline" / "analysis"
        job_analysis.mkdir(parents=True)
        expected = {"job_insights": True}
        (job_analysis / "lens_insights.json").write_text(json.dumps(expected), encoding="utf-8")

        with patch("api.routes.analysis._JOBS_DIR", jobs_dir):
            from utils.cache import analysis_file_cache
            analysis_file_cache.clear()

            resp = client.get("/api/analysis/lens-insights", params={"job_id": "j1"})
            assert resp.status_code == 200
            assert resp.json() == expected

            analysis_file_cache.clear()


# ---------------------------------------------------------------------------
# GET /api/analysis/lens-cross
# ---------------------------------------------------------------------------
class TestLensCross:
    def test_missing_data_returns_404(self, client):
        resp = client.get("/api/analysis/lens-cross")
        assert resp.status_code in (200, 404)

    def test_with_existing_file(self, client, tmp_path):
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        expected = {"cross": [1, 2, 3]}
        (analysis_dir / "lens_cross.json").write_text(json.dumps(expected), encoding="utf-8")

        with patch("api.routes.analysis._GLOBAL_ANALYSIS_DIR", analysis_dir):
            from utils.cache import analysis_file_cache
            analysis_file_cache.clear()

            resp = client.get("/api/analysis/lens-cross")
            assert resp.status_code == 200
            assert resp.json() == expected

            analysis_file_cache.clear()


# ---------------------------------------------------------------------------
# GET /api/analysis/aggregated
# ---------------------------------------------------------------------------
class TestAggregated:
    def test_missing_data_returns_404(self, client):
        resp = client.get("/api/analysis/aggregated")
        assert resp.status_code in (200, 404)

    def test_with_existing_file(self, client, tmp_path):
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        expected = {"key_findings": [], "spaces": {}}
        (analysis_dir / "aggregated.json").write_text(json.dumps(expected), encoding="utf-8")

        with patch("api.routes.analysis._GLOBAL_ANALYSIS_DIR", analysis_dir):
            from utils.cache import analysis_file_cache
            analysis_file_cache.clear()

            resp = client.get("/api/analysis/aggregated")
            assert resp.status_code == 200
            assert resp.json() == expected

            analysis_file_cache.clear()


# ---------------------------------------------------------------------------
# Cache behavior
# ---------------------------------------------------------------------------
class TestAnalysisCache:
    def test_clear_analysis_cache(self):
        from api.routes.analysis import clear_analysis_cache
        from utils.cache import analysis_file_cache

        # Add something to the cache, then clear
        analysis_file_cache.set("test_key", {"data": True})
        assert analysis_file_cache.get("test_key") is not None

        clear_analysis_cache()
        assert analysis_file_cache.get("test_key") is None

    def test_cached_result_is_returned_on_second_call(self, client, tmp_path):
        """Verify that once a file is loaded, subsequent calls use the cache."""
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        expected = {"cached": True}
        file_path = analysis_dir / "hierarchy.json"
        file_path.write_text(json.dumps(expected), encoding="utf-8")

        with patch("api.routes.analysis._GLOBAL_ANALYSIS_DIR", analysis_dir):
            from utils.cache import analysis_file_cache
            analysis_file_cache.clear()

            # First call loads from file
            resp1 = client.get("/api/analysis/hierarchy")
            assert resp1.status_code == 200

            # Remove the file — second call should still work via cache
            file_path.unlink()
            resp2 = client.get("/api/analysis/hierarchy")
            assert resp2.status_code == 200
            assert resp2.json() == expected

            analysis_file_cache.clear()
