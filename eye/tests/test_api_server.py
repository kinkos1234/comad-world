"""Tests for api/server.py — app-level endpoints (health, system-status, error handler)."""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest

fastapi = pytest.importorskip("fastapi", reason="fastapi not installed")
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api.server import app
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------
class TestHealth:
    def test_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "comadeye"

    def test_health_response_structure(self, client):
        resp = client.get("/api/health")
        data = resp.json()
        assert set(data.keys()) == {"status", "service"}


# ---------------------------------------------------------------------------
# GET /api/system-status
# ---------------------------------------------------------------------------
class TestSystemStatus:
    def test_returns_status_fields(self, client):
        """system-status should always return neo4j/ollama fields regardless of connectivity."""
        resp = client.get("/api/system-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "neo4j" in data
        assert "ollama" in data
        assert isinstance(data["neo4j"], bool)
        assert isinstance(data["ollama"], bool)

    def test_neo4j_healthy(self, client):
        """When Neo4j is reachable, neo4j should be True."""
        mock_client = MagicMock()
        mock_client.query.return_value = [{"1": 1}]
        mock_client.close.return_value = None

        mock_device = MagicMock()
        mock_device.total_ram_gb = 16.0
        mock_device.cpu_cores = 8
        mock_device.gpu_type = "apple_silicon"
        mock_device.os_name = "Darwin"
        mock_device.arch = "arm64"

        mock_settings = MagicMock()
        mock_settings.neo4j = MagicMock()
        mock_settings.llm.base_url = "http://localhost:11434/v1"
        mock_settings.llm.model = "auto"

        with patch("comad_eye.config.load_settings", return_value=mock_settings):
            with patch("comad_eye.graph.neo4j_client.Neo4jClient", return_value=mock_client):
                with patch("comad_eye.device.detect_device", return_value=mock_device):
                    # Ollama will fail (not patched), but that's fine
                    resp = client.get("/api/system-status")
                    data = resp.json()
                    assert data["neo4j"] is True

    def test_neo4j_unhealthy(self, client):
        """When Neo4j connection fails, neo4j should be False with error."""
        with patch("comad_eye.config.load_settings") as mock_settings:
            mock_settings.return_value = MagicMock()
            with patch("comad_eye.graph.neo4j_client.Neo4jClient", side_effect=Exception("Connection refused")):
                resp = client.get("/api/system-status")
                data = resp.json()
                assert data["neo4j"] is False
                assert "neo4j_error" in data

    def test_ollama_healthy(self, client):
        """When Ollama is reachable with models, ollama should be True."""
        mock_httpx_resp = MagicMock()
        mock_httpx_resp.status_code = 200
        mock_httpx_resp.json.return_value = {
            "models": [
                {"name": "llama3.1:8b"},
                {"name": "qwen2:7b"},
            ]
        }

        mock_device = MagicMock()
        mock_device.total_ram_gb = 16.0
        mock_device.cpu_cores = 8
        mock_device.gpu_type = "apple_silicon"
        mock_device.os_name = "Darwin"
        mock_device.arch = "arm64"

        mock_rec = MagicMock()
        mock_rec.name = "llama3.1:8b"
        mock_rec.size_gb = 4.5
        mock_rec.parameter_size = "8B"
        mock_rec.fitness = "safe"
        mock_rec.reason = "Fits in RAM"

        mock_settings = MagicMock()
        mock_settings.neo4j = MagicMock()
        mock_settings.llm.base_url = "http://localhost:11434/v1"
        mock_settings.llm.model = "auto"

        with patch("comad_eye.config.load_settings", return_value=mock_settings):
            with patch("comad_eye.graph.neo4j_client.Neo4jClient", side_effect=Exception("no neo4j")):
                with patch("comad_eye.device.detect_device", return_value=mock_device):
                    with patch("comad_eye.device.evaluate_all_models", return_value=[mock_rec]):
                        with patch("httpx.get", return_value=mock_httpx_resp):
                            resp = client.get("/api/system-status")
                            data = resp.json()
                            assert data["ollama"] is True
                            assert "llama3.1:8b" in data["available_models"]
                            assert len(data["model_recommendations"]) == 1

    def test_ollama_non_200_response(self, client):
        """When Ollama returns non-200, ollama should be False with error."""
        mock_httpx_resp = MagicMock()
        mock_httpx_resp.status_code = 503

        mock_settings = MagicMock()
        mock_settings.neo4j = MagicMock()
        mock_settings.llm.base_url = "http://localhost:11434/v1"
        mock_settings.llm.model = "auto"

        with patch("comad_eye.config.load_settings", return_value=mock_settings):
            with patch("comad_eye.graph.neo4j_client.Neo4jClient", side_effect=Exception("no neo4j")):
                with patch("comad_eye.device.detect_device", side_effect=Exception("no device")):
                    with patch("httpx.get", return_value=mock_httpx_resp):
                        resp = client.get("/api/system-status")
                        data = resp.json()
                        assert data["ollama"] is False
                        assert "ollama_error" in data

    def test_ollama_connection_error(self, client):
        """When Ollama is unreachable, ollama should be False with error."""
        mock_settings = MagicMock()
        mock_settings.neo4j = MagicMock()
        mock_settings.llm.base_url = "http://localhost:11434/v1"
        mock_settings.llm.model = "auto"

        with patch("comad_eye.config.load_settings", return_value=mock_settings):
            with patch("comad_eye.graph.neo4j_client.Neo4jClient", side_effect=Exception("no neo4j")):
                with patch("comad_eye.device.detect_device", side_effect=Exception("no device")):
                    with patch("httpx.get", side_effect=Exception("Connection refused")):
                        resp = client.get("/api/system-status")
                        data = resp.json()
                        assert data["ollama"] is False
                        assert "ollama_error" in data

    def test_device_detection_included(self, client):
        """Device info should be included in system status."""
        resp = client.get("/api/system-status")
        data = resp.json()
        assert "device" in data

    def test_model_selection_with_explicit_model(self, client):
        """When model is explicitly configured and available, it should be selected."""
        mock_httpx_resp = MagicMock()
        mock_httpx_resp.status_code = 200
        mock_httpx_resp.json.return_value = {
            "models": [
                {"name": "llama3.1:8b"},
                {"name": "qwen2:7b"},
            ]
        }

        mock_settings = MagicMock()
        mock_settings.neo4j = MagicMock()
        mock_settings.llm.base_url = "http://localhost:11434/v1"
        mock_settings.llm.model = "llama3.1:8b"

        with patch("comad_eye.config.load_settings", return_value=mock_settings):
            with patch("comad_eye.graph.neo4j_client.Neo4jClient", side_effect=Exception("no neo4j")):
                with patch("comad_eye.device.detect_device", side_effect=Exception("no device")):
                    with patch("httpx.get", return_value=mock_httpx_resp):
                        resp = client.get("/api/system-status")
                        data = resp.json()
                        assert data["llm_model"] == "llama3.1:8b"

    def test_model_selection_auto_picks_first(self, client):
        """When model='auto', it should pick the first available model."""
        mock_httpx_resp = MagicMock()
        mock_httpx_resp.status_code = 200
        mock_httpx_resp.json.return_value = {
            "models": [
                {"name": "qwen2:7b"},
                {"name": "llama3.1:8b"},
            ]
        }

        mock_settings = MagicMock()
        mock_settings.neo4j = MagicMock()
        mock_settings.llm.base_url = "http://localhost:11434/v1"
        mock_settings.llm.model = "auto"

        with patch("comad_eye.config.load_settings", return_value=mock_settings):
            with patch("comad_eye.graph.neo4j_client.Neo4jClient", side_effect=Exception("no neo4j")):
                with patch("comad_eye.device.detect_device", side_effect=Exception("no device")):
                    with patch("httpx.get", return_value=mock_httpx_resp):
                        resp = client.get("/api/system-status")
                        data = resp.json()
                        assert data["llm_model"] == "qwen2:7b"

    def test_no_available_models_uses_config(self, client):
        """When no models available, fall back to configured model name."""
        mock_httpx_resp = MagicMock()
        mock_httpx_resp.status_code = 200
        mock_httpx_resp.json.return_value = {"models": []}

        mock_settings = MagicMock()
        mock_settings.neo4j = MagicMock()
        mock_settings.llm.base_url = "http://localhost:11434/v1"
        mock_settings.llm.model = "some-model"

        with patch("comad_eye.config.load_settings", return_value=mock_settings):
            with patch("comad_eye.graph.neo4j_client.Neo4jClient", side_effect=Exception("no neo4j")):
                with patch("comad_eye.device.detect_device", side_effect=Exception("no device")):
                    with patch("httpx.get", return_value=mock_httpx_resp):
                        resp = client.get("/api/system-status")
                        data = resp.json()
                        assert data["llm_model"] == "some-model"


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------
class TestGlobalExceptionHandler:
    def test_unhandled_exception_returns_500(self, client):
        """Injecting an error on a route should trigger the global handler."""
        from api.server import app

        # Add a temporary route that always raises
        @app.get("/api/_test_error_route")
        async def _raise_error():
            raise RuntimeError("Test deliberate error")

        resp = client.get("/api/_test_error_route")
        assert resp.status_code == 500
        data = resp.json()
        assert data["error"] == "Internal server error"
        assert data["code"] == "INTERNAL_ERROR"
        assert "Test deliberate error" in data["detail"]

    def test_404_for_unknown_routes(self, client):
        resp = client.get("/api/totally_unknown_route")
        assert resp.status_code in (404, 405)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
class TestCORS:
    def test_cors_headers_for_allowed_origin(self, client):
        resp = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_cors_not_set_for_disallowed_origin(self, client):
        resp = client.options(
            "/api/health",
            headers={
                "Origin": "http://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") != "http://evil.com"

    def test_cors_headers_respect_env_allowlist(self, monkeypatch):
        monkeypatch.setenv(
            "CORS_ALLOW_ORIGINS",
            "https://eye.example.com, https://ops.example.com",
        )
        sys.modules.pop("api.server", None)
        server = importlib.import_module("api.server")
        client = TestClient(server.app, raise_server_exceptions=False)

        resp = client.options(
            "/api/health",
            headers={
                "Origin": "https://ops.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "https://ops.example.com"

        monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
        sys.modules.pop("api.server", None)
        importlib.import_module("api.server")


# ---------------------------------------------------------------------------
# Router inclusion verification
# ---------------------------------------------------------------------------
class TestRouterInclusion:
    """Verify that all expected routers are mounted on the app."""

    def test_pipeline_routes_mounted(self, client):
        resp = client.get("/api/jobs")
        assert resp.status_code == 200

    def test_analysis_routes_mounted(self, client):
        resp = client.get("/api/analysis/lenses")
        assert resp.status_code == 200

    def test_graph_routes_respond(self, client):
        with patch("api.routes.graph._get_client") as mock_gc:
            mock_gc.return_value = MagicMock(query=MagicMock(return_value=[]), close=MagicMock())
            resp = client.get("/api/graph/entities")
            assert resp.status_code == 200

    def test_qa_routes_mounted(self, client):
        resp = client.post("/api/qa/ask", json={})
        assert resp.status_code == 422

    def test_report_routes_mounted(self, client, tmp_path):
        with patch("api.routes.report.REPORTS_DIR", tmp_path):
            resp = client.get("/api/report/some_id")
            assert resp.status_code == 404
