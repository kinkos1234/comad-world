"""설정 로더 — Pydantic 기반 settings.yaml 파싱/검증 + 환경변수 오버라이드"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class Neo4jSettings(BaseModel):
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = ""
    database: str = "neo4j"


class TaskLLMOverrides(BaseModel):
    """태스크별 LLM 파라미터 오버라이드."""

    temperature: float | None = None
    max_tokens: int | None = None
    num_ctx: int | None = None


class LLMSettings(BaseModel):
    base_url: str = "http://localhost:11434/v1"
    model: str = "qwen3.5:9b"
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 120  # 2분 — 실패 빠르게 감지
    num_ctx: int = 4096  # 로컬 모델 부하 감소

    # 태스크별 파라미터 오버라이드 (8B 로컬 모델 최적화 기본값)
    task_overrides: dict[str, TaskLLMOverrides] = Field(
        default_factory=lambda: {
            "extraction": TaskLLMOverrides(temperature=0.1, max_tokens=2048),
            "interpretation": TaskLLMOverrides(temperature=0.5, max_tokens=512),
            "quote": TaskLLMOverrides(temperature=0.6, max_tokens=512),
            "lens": TaskLLMOverrides(temperature=0.3, max_tokens=1024, num_ctx=8192),
            "summarization": TaskLLMOverrides(temperature=0.3, max_tokens=512),
        }
    )


class EmbeddingsSettings(BaseModel):
    model: str = "BAAI/bge-m3"
    device: str = "mps"
    dimension: int = 1024
    batch_size: int = 32


class IngestionSettings(BaseModel):
    chunk_size: int = 300  # 로컬 LLM 부하 감소
    chunk_overlap: int = 50
    max_entity_types: int = 15
    max_relationship_types: int = 12
    max_retries: int = 3
    extraction_concurrency: int = 1  # 로컬 LLM: 1, API LLM: 4-8


class SimulationSettings(BaseModel):
    max_rounds: int = 10
    min_rounds: int = 5  # 수렴 판정 전 최소 라운드 수
    community_refresh_interval: int = 3
    propagation_decay: float = 0.6
    propagation_max_hops: int = 3
    volatility_decay: float = 0.1
    convergence_threshold: float = 0.005  # 변화율 기반으로 낮춤
    max_actions_per_entity: int = 1
    meta_edge_entity_limit: int = 50
    meta_edge_neighbor_limit: int = 30


class AnalysisSettings(BaseModel):
    enabled_spaces: list[str] = Field(
        default_factory=lambda: [
            "hierarchy", "temporal", "recursive",
            "structural", "causal", "cross_space",
        ]
    )
    enabled_lenses: list[str] = Field(
        default_factory=lambda: [
            "sun_tzu", "adam_smith", "taleb", "kahneman", "meadows",
        ]
    )
    parallel: bool = True  # 독립 공간 병렬 실행


class ReportSettings(BaseModel):
    include_interviews: bool = True
    max_interview_quotes: int = 3
    max_sections: int = 5


class QASettings(BaseModel):
    max_conversation_history: int = 10
    vector_search_top_k: int = 3
    cypher_max_hops: int = 5


class LoggingSettings(BaseModel):
    level: str = "INFO"
    log_llm_calls: bool = True
    log_dir: str = "data/logs"


class Settings(BaseModel):
    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    embeddings: EmbeddingsSettings = Field(default_factory=EmbeddingsSettings)
    ingestion: IngestionSettings = Field(default_factory=IngestionSettings)
    simulation: SimulationSettings = Field(default_factory=SimulationSettings)
    analysis: AnalysisSettings = Field(default_factory=AnalysisSettings)
    report: ReportSettings = Field(default_factory=ReportSettings)
    qa: QASettings = Field(default_factory=QASettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


def _locate_project_root() -> Path:
    # comad_eye may sit at eye/utils/ (legacy) or eye/src/comad_eye/.
    # Walk up until we find the eye/ dir that owns config/settings.yaml.
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config" / "settings.yaml").exists():
            return parent
    return here.parent.parent


_PROJECT_ROOT = _locate_project_root()
_DEFAULT_SETTINGS_PATH = _PROJECT_ROOT / "config" / "settings.yaml"
# Overrides emitted by scripts/apply-config.sh from the umbrella
# comad.config.yaml `eye.*` section (ADR 0002 PR 3).
_OVERRIDES_PATH = _PROJECT_ROOT / "config" / "overrides.yaml"


def _reset_project_root_for_tests() -> None:
    """Tests that chdir to tmp dirs can call this to re-locate the root."""
    global _PROJECT_ROOT, _DEFAULT_SETTINGS_PATH, _OVERRIDES_PATH
    _PROJECT_ROOT = _locate_project_root()
    _DEFAULT_SETTINGS_PATH = _PROJECT_ROOT / "config" / "settings.yaml"
    _OVERRIDES_PATH = _PROJECT_ROOT / "config" / "overrides.yaml"

# 환경변수 → settings 매핑 (ENV_VAR: (section, key, type))
_ENV_MAP: dict[str, tuple[str, str, type]] = {
    "NEO4J_URI": ("neo4j", "uri", str),
    "NEO4J_USER": ("neo4j", "user", str),
    "NEO4J_PASSWORD": ("neo4j", "password", str),
    "NEO4J_DATABASE": ("neo4j", "database", str),
    "LLM_BASE_URL": ("llm", "base_url", str),
    "LLM_MODEL": ("llm", "model", str),
    "LLM_TEMPERATURE": ("llm", "temperature", float),
    "LLM_MAX_TOKENS": ("llm", "max_tokens", int),
    "LLM_TIMEOUT": ("llm", "timeout", int),
    "EMBEDDINGS_MODEL": ("embeddings", "model", str),
    "EMBEDDINGS_DEVICE": ("embeddings", "device", str),
    # Docker compose compatibility (COMADEYE_ prefix)
    "COMADEYE_NEO4J_URI": ("neo4j", "uri", str),
    "COMADEYE_OLLAMA_URL": ("llm", "base_url", str),
}


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay into base; overlay wins on leaf conflicts."""
    for key, value in overlay.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(value, dict)
        ):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _apply_config_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    """Merge eye/config/overrides.yaml (generated from comad.config.yaml)
    over the module-owned settings.yaml. Env vars still win afterwards."""
    if not _OVERRIDES_PATH.exists():
        return raw
    with open(_OVERRIDES_PATH, encoding="utf-8") as f:
        overlay: dict[str, Any] = yaml.safe_load(f) or {}
    return _deep_merge(raw, overlay)


def _apply_env_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    """환경변수가 설정되어 있으면 settings.yaml 값을 오버라이드한다."""
    for env_var, (section, key, cast) in _ENV_MAP.items():
        value = os.environ.get(env_var)
        if value is not None:
            if section not in raw:
                raw[section] = {}
            raw[section][key] = cast(value)
    return raw


def load_settings(path: Path | str | None = None) -> Settings:
    """settings.yaml을 읽고 환경변수 오버라이드를 적용하여 Settings 객체로 반환한다."""
    settings_path = Path(path) if path else _DEFAULT_SETTINGS_PATH
    if settings_path.exists():
        with open(settings_path, encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}
    else:
        raw = {}
    # Only apply overrides.yaml when loading the default settings path.
    # A caller passing a custom path is being explicit; don't merge
    # surprises on top of their input (ADR 0002 PR 3).
    if path is None:
        raw = _apply_config_overrides(raw)
    raw = _apply_env_overrides(raw)
    return Settings(**raw)


def load_yaml(path: Path | str) -> dict[str, Any]:
    """범용 YAML 로더."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def project_root() -> Path:
    """프로젝트 루트 경로를 반환한다."""
    return _PROJECT_ROOT
