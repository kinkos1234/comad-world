"""스냅샷 작성기 — 라운드별 그래프 상태 직렬화"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from comad_eye.graph.neo4j_client import Neo4jClient

logger = logging.getLogger("comadeye")


class SnapshotWriter:
    """라운드별 그래프 상태 변경분을 JSONL로 기록한다."""

    def __init__(self, client: Neo4jClient, output_dir: str = "data/snapshots"):
        self._client = client
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def save(self, round_num: int, changes: dict[str, Any]) -> Path:
        """라운드 스냅샷을 저장한다."""
        snapshot = {
            "round": round_num,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "events_injected": len(changes.get("events", [])),
            "propagation_effects": len(changes.get("propagation", [])),
            "meta_edges_fired": len(changes.get("meta_edges", [])),
            "actions_executed": len(changes.get("actions", [])),
            "community_migrations": len(changes.get("migrations", [])),
            "changes": self._serialize_changes(changes),
            "summary": self._get_summary(),
        }

        path = self._output_dir / f"round_{round_num:03d}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")

        return path

    def _serialize_changes(self, changes: dict[str, Any]) -> dict[str, Any]:
        """변경 내역을 직렬화 가능한 형태로 변환한다."""
        serializable: dict[str, Any] = {}

        if "events" in changes:
            serializable["events"] = [
                {"uid": e.uid, "name": e.name, "magnitude": e.magnitude}
                for e in changes["events"]
            ]

        if "propagation" in changes:
            serializable["propagation"] = changes["propagation"][:20]

        if "meta_edges" in changes:
            serializable["meta_edges"] = changes["meta_edges"][:20]

        if "actions" in changes:
            serializable["actions"] = [
                {
                    "action": a.get("action"),
                    "actor": a.get("actor"),
                    "actor_name": a.get("actor_name"),
                }
                for a in changes.get("actions", [])
            ]

        if "migrations" in changes:
            serializable["migrations"] = changes["migrations"]

        return serializable

    def _get_summary(self) -> dict[str, Any]:
        """현재 그래프의 요약 통계를 반환한다."""
        stats = self._client.get_graph_stats()

        # stance 분포 (히스토그램)
        stance_dist = self._client.query(
            "MATCH (n:Entity) "
            "RETURN "
            "  count(CASE WHEN n.stance < -0.5 THEN 1 END) AS very_neg, "
            "  count(CASE WHEN n.stance >= -0.5 AND n.stance < 0 THEN 1 END) AS neg, "
            "  count(CASE WHEN n.stance >= 0 AND n.stance < 0.5 THEN 1 END) AS pos, "
            "  count(CASE WHEN n.stance >= 0.5 THEN 1 END) AS very_pos"
        )

        # 커뮤니티 수
        comm = self._client.query(
            "MATCH (n:Entity) WHERE n.community_id IS NOT NULL "
            "RETURN count(DISTINCT n.community_id) AS cnt"
        )

        return {
            "node_count": stats.get("node_count", 0),
            "active_edge_count": stats.get("edge_count", 0),
            "avg_volatility": stats.get("avg_volatility", 0),
            "avg_stance": stats.get("avg_stance", 0),
            "stance_distribution": stance_dist[0] if stance_dist else {},
            "community_count": comm[0]["cnt"] if comm else 0,
            "relationship_distribution": stats.get("relationship_distribution", {}),
        }

    def check_invariants(self) -> list[str]:
        """불변량을 체크하고 위반 사항을 반환한다."""
        violations = []

        # stance 범위
        bad_stance = self._client.query(
            "MATCH (n:Entity) WHERE n.stance < -1.0 OR n.stance > 1.0 "
            "RETURN n.uid AS uid, n.stance AS val"
        )
        for r in bad_stance:
            violations.append(f"stance 범위 위반: {r['uid']} = {r['val']}")

        # volatility 범위
        bad_vol = self._client.query(
            "MATCH (n:Entity) WHERE n.volatility < 0.0 OR n.volatility > 1.0 "
            "RETURN n.uid AS uid, n.volatility AS val"
        )
        for r in bad_vol:
            violations.append(f"volatility 범위 위반: {r['uid']} = {r['val']}")

        # 자기참조
        self_ref = self._client.query(
            "MATCH (n)-[r]->(n) RETURN count(r) AS cnt"
        )
        if self_ref and self_ref[0]["cnt"] > 0:
            violations.append(f"자기참조 엣지: {self_ref[0]['cnt']}개")

        return violations

    @staticmethod
    def load_snapshots(snapshot_dir: str | Path) -> list[dict[str, Any]]:
        """스냅샷 디렉토리에서 모든 스냅샷을 로드한다."""
        snapshots = []
        snapshot_dir = Path(snapshot_dir)
        for path in sorted(snapshot_dir.glob("round_*.jsonl")):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    snapshots.append(json.loads(line.strip()))
        return snapshots
