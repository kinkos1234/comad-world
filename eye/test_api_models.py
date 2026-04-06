"""Tests for api/models.py — Pydantic request/response model validation."""

from __future__ import annotations

import pytest


class TestRunPipelineRequest:
    def test_valid_minimal(self):
        from api.models import RunPipelineRequest
        req = RunPipelineRequest(seed_text="This is a valid seed text with enough chars")
        assert req.seed_text == "This is a valid seed text with enough chars"
        assert req.max_rounds == 10  # default
        assert req.propagation_decay == 0.6  # default
        assert req.max_hops == 3  # default
        assert req.lenses is None
        assert req.resume_from_cache is True  # default

    def test_valid_full(self):
        from api.models import RunPipelineRequest
        req = RunPipelineRequest(
            seed_text="A sufficiently long seed text for testing.",
            analysis_prompt="Political dynamics",
            model="llama3.1:8b",
            max_rounds=25,
            propagation_decay=0.8,
            max_hops=5,
            volatility_decay=0.05,
            convergence_threshold=0.02,
            lenses=["sun_tzu", "machiavelli"],
            resume_from_cache=False,
        )
        assert req.max_rounds == 25
        assert req.lenses == ["sun_tzu", "machiavelli"]
        assert req.resume_from_cache is False

    def test_seed_text_too_short(self):
        from api.models import RunPipelineRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RunPipelineRequest(seed_text="short")

    def test_empty_seed_text_rejected(self):
        from api.models import RunPipelineRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RunPipelineRequest(seed_text="")

    def test_max_rounds_too_low(self):
        from api.models import RunPipelineRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RunPipelineRequest(seed_text="Valid long seed text here.", max_rounds=0)

    def test_max_rounds_too_high(self):
        from api.models import RunPipelineRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RunPipelineRequest(seed_text="Valid long seed text here.", max_rounds=51)

    def test_propagation_decay_out_of_range(self):
        from api.models import RunPipelineRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RunPipelineRequest(seed_text="Valid long seed text here.", propagation_decay=1.5)

    def test_max_hops_out_of_range(self):
        from api.models import RunPipelineRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RunPipelineRequest(seed_text="Valid long seed text here.", max_hops=11)


class TestQARequest:
    def test_valid(self):
        from api.models import QARequest
        req = QARequest(question="What happened?", job_id="abc123")
        assert req.question == "What happened?"

    def test_empty_question_rejected(self):
        from api.models import QARequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            QARequest(question="", job_id="abc123")

    def test_missing_job_id_rejected(self):
        from api.models import QARequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            QARequest(question="What?")


class TestPreflightRequest:
    def test_valid_minimal(self):
        from api.models import PreflightRequest
        req = PreflightRequest(seed_text="Some text here")
        assert req.chunk_size == 600  # default
        assert req.chunk_overlap == 100  # default
        assert req.batch_size == 2  # default

    def test_empty_text_rejected(self):
        from api.models import PreflightRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PreflightRequest(seed_text="")

    def test_chunk_size_too_small(self):
        from api.models import PreflightRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PreflightRequest(seed_text="Text", chunk_size=50)

    def test_batch_size_too_small(self):
        from api.models import PreflightRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PreflightRequest(seed_text="Text", batch_size=0)


class TestJobResponse:
    def test_job_response(self):
        from api.models import JobResponse, JobStatus
        resp = JobResponse(job_id="abc123", status=JobStatus.PENDING)
        assert resp.job_id == "abc123"
        assert resp.status == JobStatus.PENDING


class TestStageUpdate:
    def test_stage_update_defaults(self):
        from api.models import JobStatus, PipelineStage, StageUpdate
        update = StageUpdate(stage=PipelineStage.INGESTION, status=JobStatus.RUNNING)
        assert update.message == ""
        assert update.data == {}

    def test_stage_update_with_data(self):
        from api.models import JobStatus, PipelineStage, StageUpdate
        update = StageUpdate(
            stage=PipelineStage.ANALYSIS,
            status=JobStatus.COMPLETED,
            message="Done",
            data={"key_findings_count": 5},
        )
        assert update.data["key_findings_count"] == 5


class TestQAResponse:
    def test_qa_response_defaults(self):
        from api.models import QAResponse
        resp = QAResponse(answer="The answer is 42.")
        assert resp.follow_ups == []
        assert resp.context == {}


class TestPreflightResponse:
    def test_preflight_response(self):
        from api.models import PreflightResponse
        resp = PreflightResponse(
            chars=100, estimated_tokens=25, sentences=5,
            risk_level="low", recommended_batch_size=2,
            expected_batches=3, expected_llm_calls=6,
        )
        assert resp.chars == 100
        assert resp.warnings == []


class TestSystemStatus:
    def test_system_status_defaults(self):
        from api.models import SystemStatus
        status = SystemStatus()
        assert status.neo4j is False
        assert status.ollama is False
        assert status.llm_model == ""
        assert status.available_models == []
        assert status.model_recommendations == []

    def test_system_status_model_dump(self):
        from api.models import SystemStatus
        status = SystemStatus(neo4j=True, ollama=True, llm_model="llama3")
        data = status.model_dump()
        assert data["neo4j"] is True
        assert data["llm_model"] == "llama3"


class TestDeviceInfoResponse:
    def test_defaults(self):
        from api.models import DeviceInfoResponse
        info = DeviceInfoResponse()
        assert info.total_ram_gb == 0.0
        assert info.cpu_cores == 0
        assert info.gpu_type == ""


class TestModelRecommendationResponse:
    def test_defaults(self):
        from api.models import ModelRecommendationResponse
        rec = ModelRecommendationResponse(name="test-model")
        assert rec.fitness == "unknown"
        assert rec.reason == ""


class TestErrorResponse:
    def test_error_response(self):
        from api.models import ErrorResponse
        err = ErrorResponse(error="Something went wrong", code="BAD_REQUEST", detail="Details here")
        assert err.error == "Something went wrong"
        assert err.code == "BAD_REQUEST"

    def test_error_response_defaults(self):
        from api.models import ErrorResponse
        err = ErrorResponse(error="Oops")
        assert err.code == "UNKNOWN_ERROR"
        assert err.detail == ""


class TestEnums:
    def test_pipeline_stage_values(self):
        from api.models import PipelineStage
        assert PipelineStage.INGESTION.value == "ingestion"
        assert PipelineStage.GRAPH.value == "graph"
        assert PipelineStage.COMMUNITY.value == "community"
        assert PipelineStage.SIMULATION.value == "simulation"
        assert PipelineStage.ANALYSIS.value == "analysis"
        assert PipelineStage.REPORT.value == "report"

    def test_job_status_values(self):
        from api.models import JobStatus
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"

    def test_pipeline_stage_is_string(self):
        from api.models import PipelineStage
        assert isinstance(PipelineStage.INGESTION, str)
        assert PipelineStage.INGESTION == "ingestion"

    def test_job_status_is_string(self):
        from api.models import JobStatus
        assert isinstance(JobStatus.PENDING, str)
        assert JobStatus.PENDING == "pending"
