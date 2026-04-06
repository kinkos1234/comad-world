"""Active Metadata 버스 — 변경 전파 이벤트 시스템"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from utils.config import load_yaml, project_root

logger = logging.getLogger("comadeye")


@dataclass
class ChangeEvent:
    """변경 이벤트."""
    source: str
    target: str
    property: str = ""
    old_value: Any = None
    new_value: Any = None
    round: int = -1
    caused_by: str = ""
    event_type: str = "property_change"  # property_change | cascade | config_change
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ActiveMetadataBus:
    """시스템 전체의 변경 전파를 관리하는 이벤트 버스."""

    def __init__(self, bindings_path: str | None = None):
        path = bindings_path or str(project_root() / "config" / "bindings.yaml")
        self._bindings = load_yaml(path)
        self._listeners: dict[str, list[Callable[[ChangeEvent], None]]] = {}
        self._change_log: list[ChangeEvent] = []
        self._invalidated: set[str] = set()
        self._stale_communities: set[str] = set()

    @property
    def change_log(self) -> list[ChangeEvent]:
        return self._change_log

    @property
    def invalidated(self) -> set[str]:
        return self._invalidated

    @property
    def stale_communities(self) -> set[str]:
        return self._stale_communities

    def subscribe(self, event_type: str, callback: Callable[[ChangeEvent], None]) -> None:
        """이벤트 타입에 리스너를 등록한다."""
        self._listeners.setdefault(event_type, []).append(callback)

    def emit(self, event: ChangeEvent) -> None:
        """변경 이벤트를 발행하고 등록된 리스너에 전파한다."""
        self._change_log.append(event)

        # 리스너 호출
        for callback in self._listeners.get(event.event_type, []):
            try:
                callback(event)
            except Exception as e:
                logger.warning(f"Active Metadata 리스너 오류: {e}")

        # 설정 파일 변경 시 bindings.yaml 기반 전파
        if event.event_type == "config_change":
            self._propagate_config_change(event)

    def emit_property_change(
        self,
        entity_uid: str,
        prop: str,
        old_val: Any,
        new_val: Any,
        round_num: int = -1,
        caused_by: str = "",
    ) -> None:
        """엔티티 속성 변경 이벤트를 발행한다."""
        event = ChangeEvent(
            source=entity_uid,
            target=entity_uid,
            property=prop,
            old_value=old_val,
            new_value=new_val,
            round=round_num,
            caused_by=caused_by,
            event_type="property_change",
        )
        self.emit(event)

    def mark_community_stale(self, community_id: str) -> None:
        """커뮤니티 요약을 stale 상태로 마킹한다."""
        self._stale_communities.add(community_id)

    def invalidate_analysis_cache(
        self,
        entity_uid: str,
        spaces: list[str] | None = None,
    ) -> None:
        """분석 캐시를 무효화한다."""
        target_spaces = spaces or ["structural", "causal"]
        for space in target_spaces:
            self._invalidated.add(f"{space}:{entity_uid}")

    def _propagate_config_change(self, event: ChangeEvent) -> None:
        """bindings.yaml의 change_propagation 규칙에 따라 전파한다."""
        rules = self._bindings.get("change_propagation", [])
        for rule in rules:
            trigger = rule.get("when", "")
            if event.source in trigger:
                meta = rule.get("active_metadata", {})
                action = meta.get("action", "notify")
                message = meta.get("message", "")

                for target in rule.get("propagate_to", []):
                    if action == "invalidate_downstream":
                        self._invalidated.add(target)
                        logger.info(
                            f"[Active Metadata] {event.source} → {target} 캐시 무효화"
                        )
                    elif action == "notify":
                        logger.info(
                            f"[Active Metadata] {event.source} → {target}: {message}"
                        )

                    # 연쇄 이벤트
                    cascade = ChangeEvent(
                        source=event.source,
                        target=target,
                        caused_by=f"cascade:{event.source}",
                        event_type="cascade",
                    )
                    self._change_log.append(cascade)

    def reset(self) -> None:
        """라운드 간 임시 상태를 초기화한다."""
        self._invalidated.clear()

    def get_summary(self) -> dict[str, Any]:
        """변경 이벤트 요약을 반환한다."""
        return {
            "total_events": len(self._change_log),
            "invalidated_count": len(self._invalidated),
            "stale_communities": len(self._stale_communities),
            "event_types": _count_by(
                self._change_log, lambda e: e.event_type
            ),
        }


def _count_by(items: list, key_fn: Callable) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        k = key_fn(item)
        counts[k] = counts.get(k, 0) + 1
    return counts
