"""Preflight — 입력 사전 진단 (토큰 추정, 위험도, 배치 수 예측)"""

from __future__ import annotations

from dataclasses import dataclass

import tiktoken


@dataclass
class PreflightResult:
    """사전 진단 결과."""

    chars: int
    estimated_tokens: int
    sentences: int
    risk_level: str  # "low" | "medium" | "high"
    recommended_batch_size: int
    expected_batches: int
    expected_llm_calls: int
    warnings: list[str]


# 토큰 수 기준 위험도
_RISK_THRESHOLDS = {
    "low": 3000,      # ~3000 토큰: 안전
    "medium": 8000,    # ~8000 토큰: 주의
    # 그 이상: high
}

# 청크 사이즈 (chunker 기본값)
_DEFAULT_CHUNK_SIZE = 300
_DEFAULT_OVERLAP = 50


def run_preflight(
    text: str,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = _DEFAULT_OVERLAP,
    batch_size: int = 1,
) -> PreflightResult:
    """입력 텍스트를 분석하여 사전 진단 결과를 반환한다."""
    encoder = tiktoken.get_encoding("cl100k_base")

    chars = len(text)
    tokens = len(encoder.encode(text))

    # 간이 문장 수 추정 (마침표/물음표/느낌표 기준)
    sentences = sum(1 for c in text if c in ".?!。")
    sentences = max(sentences, 1)

    # 위험도 판정
    if tokens <= _RISK_THRESHOLDS["low"]:
        risk = "low"
    elif tokens <= _RISK_THRESHOLDS["medium"]:
        risk = "medium"
    else:
        risk = "high"

    # 예상 청크 수 계산
    effective_chunk = chunk_size - chunk_overlap
    estimated_chunks = max(1, (tokens + effective_chunk - 1) // effective_chunk)
    expected_batches = max(1, (estimated_chunks + batch_size - 1) // batch_size)

    # LLM 호출 수 예측 (추출 + 잠재적 2차 관계 추출)
    expected_llm_calls = expected_batches  # 최소 추출
    if risk == "high":
        expected_llm_calls *= 2  # 2차 관계 추출 가능성

    # 경고 메시지
    warnings: list[str] = []
    if risk == "high":
        warnings.append(
            f"입력이 깁니다 (약 {tokens:,}토큰). "
            f"처리 시간이 길어질 수 있습니다."
        )
    if tokens > 15000:
        warnings.append(
            "입력이 매우 깁니다. 핵심 내용만 추려서 입력하는 것을 권장합니다."
        )

    return PreflightResult(
        chars=chars,
        estimated_tokens=tokens,
        sentences=sentences,
        risk_level=risk,
        recommended_batch_size=batch_size,
        expected_batches=expected_batches,
        expected_llm_calls=expected_llm_calls,
        warnings=warnings,
    )
