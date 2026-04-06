"""Pydantic request/response models for the ComadEye API."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Enums ---

class PipelineStage(str, Enum):
    INGESTION = "ingestion"
    GRAPH = "graph"
    COMMUNITY = "community"
    SIMULATION = "simulation"
    ANALYSIS = "analysis"
    REPORT = "report"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# --- Request Models ---

class RunPipelineRequest(BaseModel):
    seed_text: str = Field(..., min_length=10, description="시드 데이터 텍스트")
    analysis_prompt: str | None = Field(None, description="분석 주제/관점 (선택)")
    model: str | None = Field(None, description="사용할 LLM 모델 (선택, 미지정 시 자동 감지)")
    max_rounds: int = Field(10, ge=1, le=50)
    propagation_decay: float = Field(0.6, ge=0.0, le=1.0)
    max_hops: int = Field(3, ge=1, le=10)
    volatility_decay: float = Field(0.1, ge=0.0, le=1.0)
    convergence_threshold: float = Field(0.01, ge=0.0, le=1.0)
    lenses: list[str] | None = Field(
        None,
        description="활성화할 분석 렌즈 ID 목록 (선택, 미지정 시 기본 6개)",
    )
    resume_from_cache: bool = Field(
        True,
        description="이전 추출 캐시 재사용 여부 (동일 입력 재실행 시 속도 향상)",
    )


class QARequest(BaseModel):
    question: str = Field(..., min_length=1)
    job_id: str = Field(..., description="분석 작업 ID")


# --- Response Models ---

class JobResponse(BaseModel):
    job_id: str
    status: JobStatus


class StageUpdate(BaseModel):
    stage: PipelineStage
    status: JobStatus
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class AnalysisSpaceResult(BaseModel):
    name: str
    summary: str = ""
    confidence: float = 0.0
    data: dict[str, Any] = Field(default_factory=dict)


class KeyFinding(BaseModel):
    rank: int
    finding: str
    supporting_spaces: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class AggregatedAnalysis(BaseModel):
    simulation_summary: dict[str, Any] = Field(default_factory=dict)
    key_findings: list[KeyFinding] = Field(default_factory=list)
    spaces: dict[str, AnalysisSpaceResult] = Field(default_factory=dict)


class EntitySummary(BaseModel):
    uid: str
    name: str
    object_type: str = ""
    stance: float = 0.0
    volatility: float = 0.0
    influence_score: float = 0.0
    community_id: str | None = None


class EntityDetail(EntitySummary):
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)


class QAResponse(BaseModel):
    answer: str
    follow_ups: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class PreflightRequest(BaseModel):
    seed_text: str = Field(..., min_length=1, description="사전 진단할 시드 텍스트")
    chunk_size: int = Field(600, ge=100)
    chunk_overlap: int = Field(100, ge=0)
    batch_size: int = Field(2, ge=1)


class PreflightResponse(BaseModel):
    chars: int
    estimated_tokens: int
    sentences: int
    risk_level: str
    recommended_batch_size: int
    expected_batches: int
    expected_llm_calls: int
    warnings: list[str] = Field(default_factory=list)


class DeviceInfoResponse(BaseModel):
    total_ram_gb: float = 0.0
    cpu_cores: int = 0
    gpu_type: str = ""
    os_name: str = ""
    arch: str = ""


class ModelRecommendationResponse(BaseModel):
    name: str
    size_gb: float = 0.0
    parameter_size: str = ""
    fitness: str = "unknown"  # safe / warning / danger / unknown
    reason: str = ""


class ErrorResponse(BaseModel):
    """Standardized error response (RFC 7807 inspired)."""
    error: str
    code: str = "UNKNOWN_ERROR"
    detail: str = ""


class SystemStatus(BaseModel):
    neo4j: bool = False
    ollama: bool = False
    llm_model: str = ""
    available_models: list[str] = Field(default_factory=list)
    device: DeviceInfoResponse = Field(default_factory=DeviceInfoResponse)
    model_recommendations: list[ModelRecommendationResponse] = Field(
        default_factory=list
    )
