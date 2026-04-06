"""공통 서사 헬퍼 — report_generator와 narrative_builder가 공유한다."""

from __future__ import annotations


def clean_name(name: str) -> str:
    """엔티티 이름에서 밑줄을 제거하고 정리한다."""
    return name.replace("_", " ").strip()


def fmt_pct(value: float) -> str:
    """소수를 퍼센트로 포맷한다."""
    return f"{value * 100:.0f}%"


def fmt_score(value: float, decimals: int = 4) -> str:
    """소수점 포맷 (기본 4자리)."""
    return f"{value:.{decimals}f}"
