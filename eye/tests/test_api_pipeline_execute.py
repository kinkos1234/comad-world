"""Tests for api/routes/pipeline.py — _execute_pipeline and related helpers.
Covers the 99 uncovered lines (mostly _execute_pipeline background task)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import api.routes.pipeline  # noqa: F401 — ensure module is loaded before patch targets resolve

from api.models import JobStatus, PipelineStage


# ── _push_stage ──

class TestPushStage:
    def test_appends_stage_and_saves(self, tmp_path):
        with patch("api.routes.pipeline._JOBS_DIR", tmp_path):
            from api.routes.pipeline import _push_stage, _jobs

            job_id = "test123"
            _jobs[job_id] = {"status": JobStatus.RUNNING, "stages": []}

            _push_stage(job_id, PipelineStage.INGESTION, JobStatus.RUNNING, "processing...")

            assert len(_jobs[job_id]["stages"]) == 1
            assert _jobs[job_id]["stages"][0]["stage"] == PipelineStage.INGESTION.value

            # Cleanup
            del _jobs[job_id]


# ── _execute_pipeline ──

class TestExecutePipeline:
    def _setup_job(self, jobs_dict, job_id="exec01"):
        jobs_dict[job_id] = {
            "status": JobStatus.PENDING,
            "stages": [],
            "result": None,
            "error": None,
            "seed_text": "테스트 텍스트입니다.",
            "analysis_prompt": None,
            "model_override": None,
            "lenses": None,
            "settings_override": {},
            "resume_from_cache": False,
            "created_at": "2026-03-29T00:00:00",
        }
        return job_id

    @patch("comad_eye.pipeline.orchestrator.run_report")
    @patch("comad_eye.pipeline.orchestrator.run_analysis")
    @patch("comad_eye.pipeline.orchestrator.run_simulation")
    @patch("comad_eye.pipeline.orchestrator.run_community_detection")
    @patch("comad_eye.pipeline.orchestrator.run_graph_loading")
    @patch("comad_eye.pipeline.orchestrator.run_ingestion")
    @patch("comad_eye.config.load_settings")
    def test_successful_execution(
        self, mock_settings, mock_ingest, mock_graph, mock_community,
        mock_sim, mock_analysis, mock_report, tmp_path
    ):
        with patch("api.routes.pipeline._JOBS_DIR", tmp_path):
            from api.routes.pipeline import _execute_pipeline, _jobs

            job_id = self._setup_job(_jobs)

            # Configure mocks
            settings = MagicMock()
            settings.llm.model = "llama3.1:8b"
            settings.llm.base_url = "http://localhost:11434/v1"
            settings.llm.max_tokens = 1024
            mock_settings.return_value = settings

            mock_ontology = MagicMock()
            mock_ontology.entities = {"e1": MagicMock()}
            mock_ontology.relationships = [MagicMock()]
            mock_ingest.return_value = ([], mock_ontology, {"calls": 1, "tokens_in": 10, "tokens_out": 20, "tokens_total": 30})

            mock_client = MagicMock()
            mock_graph.return_value = mock_client
            mock_community.return_value = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "tokens_total": 0}
            mock_sim.return_value = {"total_rounds": 5, "events": 2}
            mock_analysis.return_value = {"key_findings": [{"f": 1}], "lens_insights": {}}
            mock_report.return_value = (tmp_path / "report.md", {"calls": 2, "tokens_in": 50, "tokens_out": 100, "tokens_total": 150})

            _execute_pipeline(job_id)

            assert _jobs[job_id]["status"] == JobStatus.COMPLETED
            assert _jobs[job_id]["result"]["total_rounds"] == 5
            assert _jobs[job_id]["result"]["llm_usage"]["calls"] == 3  # 1 + 0 + 2
            mock_client.close.assert_called_once()

            # Cleanup
            del _jobs[job_id]

    @patch("comad_eye.config.load_settings")
    def test_pipeline_failure_sets_failed_status(self, mock_settings, tmp_path):
        with patch("api.routes.pipeline._JOBS_DIR", tmp_path):
            from api.routes.pipeline import _execute_pipeline, _jobs

            job_id = self._setup_job(_jobs)

            settings = MagicMock()
            settings.llm.model = "test"
            settings.llm.base_url = "http://localhost:11434/v1"
            settings.llm.max_tokens = 1024
            mock_settings.return_value = settings

            # Make ingestion fail
            with patch("comad_eye.pipeline.orchestrator.run_ingestion", side_effect=RuntimeError("boom")):
                _execute_pipeline(job_id)

            assert _jobs[job_id]["status"] == JobStatus.FAILED
            assert "boom" in _jobs[job_id]["error"]

            del _jobs[job_id]

    @patch("comad_eye.pipeline.orchestrator.run_report")
    @patch("comad_eye.pipeline.orchestrator.run_analysis")
    @patch("comad_eye.pipeline.orchestrator.run_simulation")
    @patch("comad_eye.pipeline.orchestrator.run_community_detection")
    @patch("comad_eye.pipeline.orchestrator.run_graph_loading")
    @patch("comad_eye.pipeline.orchestrator.run_ingestion")
    @patch("comad_eye.config.load_settings")
    def test_model_override_applied(
        self, mock_settings, mock_ingest, mock_graph, mock_community,
        mock_sim, mock_analysis, mock_report, tmp_path
    ):
        with patch("api.routes.pipeline._JOBS_DIR", tmp_path):
            from api.routes.pipeline import _execute_pipeline, _jobs

            job_id = self._setup_job(_jobs)
            _jobs[job_id]["model_override"] = "custom-model"

            settings = MagicMock()
            settings.llm.model = "default"
            settings.llm.base_url = "http://localhost:11434/v1"
            settings.llm.max_tokens = 1024
            mock_settings.return_value = settings

            mock_ontology = MagicMock()
            mock_ontology.entities = {}
            mock_ontology.relationships = []
            mock_ingest.return_value = ([], mock_ontology, {})
            mock_graph.return_value = MagicMock()
            mock_community.return_value = {}
            mock_sim.return_value = {"total_rounds": 1}
            mock_analysis.return_value = {"key_findings": [], "lens_insights": {}}
            mock_report.return_value = (tmp_path / "r.md", {})

            _execute_pipeline(job_id)

            assert settings.llm.model == "custom-model"

            del _jobs[job_id]

    @patch("comad_eye.pipeline.orchestrator.run_report")
    @patch("comad_eye.pipeline.orchestrator.run_analysis")
    @patch("comad_eye.pipeline.orchestrator.run_simulation")
    @patch("comad_eye.pipeline.orchestrator.run_community_detection")
    @patch("comad_eye.pipeline.orchestrator.run_graph_loading")
    @patch("comad_eye.pipeline.orchestrator.run_ingestion")
    @patch("comad_eye.config.load_settings")
    def test_qwen3_model_warning_and_adjustment(
        self, mock_settings, mock_ingest, mock_graph, mock_community,
        mock_sim, mock_analysis, mock_report, tmp_path
    ):
        with patch("api.routes.pipeline._JOBS_DIR", tmp_path):
            from api.routes.pipeline import _execute_pipeline, _jobs

            job_id = self._setup_job(_jobs)
            _jobs[job_id]["model_override"] = "qwen3:8b"

            settings = MagicMock()
            settings.llm.model = "default"
            settings.llm.base_url = "http://localhost:11434/v1"
            settings.llm.max_tokens = 512  # below 2048

            mock_settings.return_value = settings

            mock_ontology = MagicMock()
            mock_ontology.entities = {}
            mock_ontology.relationships = []
            mock_ingest.return_value = ([], mock_ontology, {})
            mock_graph.return_value = MagicMock()
            mock_community.return_value = {}
            mock_sim.return_value = {"total_rounds": 1}
            mock_analysis.return_value = {"key_findings": [], "lens_insights": {}}
            mock_report.return_value = (tmp_path / "r.md", {})

            _execute_pipeline(job_id)

            # qwen3 detected: max_tokens bumped to 2048
            assert settings.llm.max_tokens == 2048

            del _jobs[job_id]

    @patch("comad_eye.pipeline.orchestrator.run_report")
    @patch("comad_eye.pipeline.orchestrator.run_analysis")
    @patch("comad_eye.pipeline.orchestrator.run_simulation")
    @patch("comad_eye.pipeline.orchestrator.run_community_detection")
    @patch("comad_eye.pipeline.orchestrator.run_graph_loading")
    @patch("comad_eye.pipeline.orchestrator.run_ingestion")
    @patch("comad_eye.config.load_settings")
    def test_auto_detect_model(
        self, mock_settings, mock_ingest, mock_graph, mock_community,
        mock_sim, mock_analysis, mock_report, tmp_path
    ):
        with patch("api.routes.pipeline._JOBS_DIR", tmp_path):
            from api.routes.pipeline import _execute_pipeline, _jobs

            job_id = self._setup_job(_jobs)
            # No model_override → auto-detect

            settings = MagicMock()
            settings.llm.model = "auto"
            settings.llm.base_url = "http://localhost:11434/v1"
            settings.llm.max_tokens = 1024
            mock_settings.return_value = settings

            mock_ontology = MagicMock()
            mock_ontology.entities = {}
            mock_ontology.relationships = []
            mock_ingest.return_value = ([], mock_ontology, {})
            mock_graph.return_value = MagicMock()
            mock_community.return_value = {}
            mock_sim.return_value = {"total_rounds": 1}
            mock_analysis.return_value = {"key_findings": [], "lens_insights": {}}
            mock_report.return_value = (tmp_path / "r.md", {})

            with patch("httpx.get") as mock_httpx:
                mock_httpx.return_value = MagicMock(
                    status_code=200,
                    json=lambda: {"models": [{"name": "llama3.1:8b"}]}
                )
                _execute_pipeline(job_id)

            assert settings.llm.model == "llama3.1:8b"

            del _jobs[job_id]

    @patch("comad_eye.pipeline.orchestrator.run_report")
    @patch("comad_eye.pipeline.orchestrator.run_analysis")
    @patch("comad_eye.pipeline.orchestrator.run_simulation")
    @patch("comad_eye.pipeline.orchestrator.run_community_detection")
    @patch("comad_eye.pipeline.orchestrator.run_graph_loading")
    @patch("comad_eye.pipeline.orchestrator.run_ingestion")
    @patch("comad_eye.config.load_settings")
    def test_settings_override_applied(
        self, mock_settings, mock_ingest, mock_graph, mock_community,
        mock_sim, mock_analysis, mock_report, tmp_path
    ):
        with patch("api.routes.pipeline._JOBS_DIR", tmp_path):
            from api.routes.pipeline import _execute_pipeline, _jobs

            job_id = self._setup_job(_jobs)
            _jobs[job_id]["settings_override"] = {"max_rounds": 20, "convergence_threshold": 0.01}

            settings = MagicMock()
            settings.llm.model = "test"
            settings.llm.base_url = "http://localhost:11434/v1"
            settings.llm.max_tokens = 1024
            settings.simulation = MagicMock()
            settings.simulation.max_rounds = 10
            settings.simulation.convergence_threshold = 0.05
            mock_settings.return_value = settings

            mock_ontology = MagicMock()
            mock_ontology.entities = {}
            mock_ontology.relationships = []
            mock_ingest.return_value = ([], mock_ontology, {})
            mock_graph.return_value = MagicMock()
            mock_community.return_value = {}
            mock_sim.return_value = {"total_rounds": 1}
            mock_analysis.return_value = {"key_findings": [], "lens_insights": {}}
            mock_report.return_value = (tmp_path / "r.md", {})

            _execute_pipeline(job_id)

            assert settings.simulation.max_rounds == 20
            assert settings.simulation.convergence_threshold == 0.01

            del _jobs[job_id]


# ── retry_job ──

class TestRetryJob:
    @pytest.mark.asyncio
    async def test_retry_creates_new_job(self, tmp_path):
        with patch("api.routes.pipeline._JOBS_DIR", tmp_path):
            from api.routes.pipeline import retry_job, _jobs

            _jobs["old123"] = {
                "status": JobStatus.FAILED,
                "seed_text": "retry text",
                "analysis_prompt": "prompt",
                "model_override": "model",
                "lenses": ["L1"],
                "settings_override": {"max_rounds": 5},
                "error": "original error",
            }

            bg = MagicMock()
            bg.add_task = MagicMock()

            result = await retry_job("old123", bg)

            assert result.status == JobStatus.PENDING
            assert result.job_id != "old123"
            # New job has the old job's settings
            new_job = _jobs[result.job_id]
            assert new_job["seed_text"] == "retry text"
            assert new_job["lenses"] == ["L1"]

            # Cleanup
            del _jobs["old123"]
            del _jobs[result.job_id]

    @pytest.mark.asyncio
    async def test_retry_nonexistent_job(self, tmp_path):
        with patch("api.routes.pipeline._JOBS_DIR", tmp_path):
            from api.routes.pipeline import retry_job

            bg = MagicMock()
            result = await retry_job("nonexistent", bg)
            assert result.status == JobStatus.FAILED
