"""Tests for pipeline orchestrator — verify module structure and imports."""

from __future__ import annotations


class TestOrchestratorImports:
    """Verify the orchestrator module exports all expected functions."""

    def test_all_functions_importable(self):
        from comad_eye.pipeline.orchestrator import (
            run_ingestion,
            run_graph_loading,
            run_community_detection,
            run_simulation,
            run_analysis,
            run_report,
        )
        assert callable(run_ingestion)
        assert callable(run_graph_loading)
        assert callable(run_community_detection)
        assert callable(run_simulation)
        assert callable(run_analysis)
        assert callable(run_report)

    def test_backward_compat_from_main(self):
        """main.py should still export _run_* functions for backward compat."""
        from main import (
            _run_ingestion,
            _run_graph_loading,
            _run_community_detection,
            _run_simulation,
            _run_analysis,
            _run_report,
        )
        assert callable(_run_ingestion)
        assert callable(_run_graph_loading)
        assert callable(_run_community_detection)
        assert callable(_run_simulation)
        assert callable(_run_analysis)
        assert callable(_run_report)


class TestConfigDockerCompat:
    """Verify Docker compose env vars are supported."""

    def test_comadeye_prefix_in_env_map(self):
        from comad_eye.config import _ENV_MAP
        assert "COMADEYE_NEO4J_URI" in _ENV_MAP
        assert "COMADEYE_OLLAMA_URL" in _ENV_MAP
        # Verify they map to correct fields
        assert _ENV_MAP["COMADEYE_NEO4J_URI"] == ("neo4j", "uri", str)
        assert _ENV_MAP["COMADEYE_OLLAMA_URL"] == ("llm", "base_url", str)
