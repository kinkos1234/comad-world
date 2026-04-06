"""분석공간 공통 베이스 — SimulationData + AnalysisSpace ABC"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from graph.neo4j_client import Neo4jClient
from simulation.snapshot import SnapshotWriter


@dataclass
class SimulationData:
    """6개 분석공간이 공유하는 시뮬레이션 결과 데이터."""

    snapshots: list[dict[str, Any]] = field(default_factory=list)
    events_log: list[dict[str, Any]] = field(default_factory=list)
    actions_log: list[dict[str, Any]] = field(default_factory=list)
    meta_edges_log: list[dict[str, Any]] = field(default_factory=list)
    communities_initial: dict[str, Any] = field(default_factory=dict)
    communities_final: dict[str, Any] = field(default_factory=dict)
    community_migrations: list[dict[str, Any]] = field(default_factory=list)
    graph: Neo4jClient | None = None

    @classmethod
    def from_snapshots(
        cls,
        snapshot_dir: str | Path,
        graph: Neo4jClient | None = None,
    ) -> SimulationData:
        """스냅샷 디렉토리에서 SimulationData를 구축한다."""
        snapshots = SnapshotWriter.load_snapshots(snapshot_dir)
        if not snapshots:
            return cls(graph=graph)

        events_log: list[dict[str, Any]] = []
        actions_log: list[dict[str, Any]] = []
        meta_edges_log: list[dict[str, Any]] = []
        community_migrations: list[dict[str, Any]] = []

        for snap in snapshots:
            changes = snap.get("changes", {})
            round_num = snap.get("round", 0)

            for event in changes.get("events", []):
                event["round"] = round_num
                events_log.append(event)

            for action in changes.get("actions", []):
                action["round"] = round_num
                actions_log.append(action)

            for meta in changes.get("meta_edges", []):
                meta["round"] = round_num
                meta_edges_log.append(meta)

            for migration in changes.get("migrations", []):
                migration["round"] = round_num
                community_migrations.append(migration)

        # 초기/최종 커뮤니티 (스냅샷에서 추출)
        communities_initial = (
            snapshots[0].get("summary", {}) if snapshots else {}
        )
        communities_final = (
            snapshots[-1].get("summary", {}) if snapshots else {}
        )

        return cls(
            snapshots=snapshots,
            events_log=events_log,
            actions_log=actions_log,
            meta_edges_log=meta_edges_log,
            communities_initial=communities_initial,
            communities_final=communities_final,
            community_migrations=community_migrations,
            graph=graph,
        )

    def get_entity_timeline(self, uid: str) -> list[dict[str, Any]]:
        """엔티티의 라운드별 속성 변화 타임라인을 구축한다."""
        timeline: list[dict[str, Any]] = []

        for snap in self.snapshots:
            round_num = snap.get("round", 0)
            changes = snap.get("changes", {})

            # 전파에 의한 변화
            for prop_change in changes.get("propagation", []):
                if prop_change.get("target") == uid:
                    timeline.append({
                        "round": round_num,
                        "source": "propagation",
                        "property": prop_change.get("property", "stance"),
                        "old": prop_change.get("old", 0),
                        "new": prop_change.get("new", 0),
                        "delta": prop_change.get("delta", 0),
                    })

            # Action에 의한 변화
            for action in changes.get("actions", []):
                if action.get("actor") == uid:
                    timeline.append({
                        "round": round_num,
                        "source": "action",
                        "action": action.get("action"),
                    })

        return timeline

    def get_stance_series(self, uid: str) -> list[float]:
        """엔티티의 라운드별 stance 시계열을 추출한다."""
        series: list[float] = []
        current = 0.0

        for snap in self.snapshots:
            changes = snap.get("changes", {})
            for prop_change in changes.get("propagation", []):
                if (
                    prop_change.get("target") == uid
                    and prop_change.get("property") == "stance"
                ):
                    current = prop_change.get("new", current)
            series.append(current)

        return series


class AnalysisSpace(ABC):
    """분석공간 추상 베이스 클래스."""

    name: str = "base"

    def __init__(self, data: SimulationData):
        self._data = data

    @abstractmethod
    def analyze(self) -> dict[str, Any]:
        """분석을 수행하고 결과를 반환한다."""

    def save(self, output_dir: str | Path) -> Path:
        """분석 결과를 JSON으로 저장한다."""
        result = self.analyze()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{self.name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return path
