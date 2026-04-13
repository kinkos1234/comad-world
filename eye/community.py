"""커뮤니티 탐지 — Leiden 4계층 커뮤니티 탐지"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import igraph as ig
import leidenalg

from comad_eye.graph.neo4j_client import Neo4jClient

logger = logging.getLogger("comadeye")


class CommunityDetector:
    """Leiden 알고리즘 기반 4계층 커뮤니티 탐지."""

    TIER_RESOLUTIONS = [2.0, 1.0, 0.5, 0.2]  # C0(세밀) ~ C3(거시)

    def __init__(self, client: Neo4jClient):
        self._client = client

    def detect(self) -> dict[str, Any]:
        """4계층 Leiden 커뮤니티를 탐지하고 Neo4j에 저장한다."""
        # 1. Neo4j에서 그래프 추출
        edges = self._client.query(
            "MATCH (a:Entity)-[r]->(b:Entity) "
            "WHERE r.expired_at IS NULL "
            "RETURN a.uid AS source, b.uid AS target, r.weight AS weight"
        )

        if not edges:
            logger.warning("그래프에 엣지가 없음, 커뮤니티 탐지 건너뜀")
            return {"communities": {}, "tier_counts": {}}

        # 2. igraph 그래프 구축
        node_set: set[str] = set()
        for e in edges:
            node_set.add(e["source"])
            node_set.add(e["target"])

        nodes = sorted(node_set)
        node_idx = {uid: i for i, uid in enumerate(nodes)}

        g = ig.Graph(n=len(nodes), directed=False)
        g.vs["uid"] = nodes

        edge_list = []
        weights = []
        for e in edges:
            src_idx = node_idx.get(e["source"])
            tgt_idx = node_idx.get(e["target"])
            if src_idx is not None and tgt_idx is not None and src_idx != tgt_idx:
                edge_list.append((src_idx, tgt_idx))
                w = float(e.get("weight") or 1.0)
                weights.append(max(w, 0.01))  # leidenalg는 음수 가중치 불가

        g.add_edges(edge_list)
        g.es["weight"] = weights

        # 3. 4계층 Leiden 탐지
        communities: dict[str, dict[str, str]] = {}  # tier -> {uid: community_id}
        tier_counts: dict[str, int] = {}

        for tier, resolution in enumerate(self.TIER_RESOLUTIONS):
            partition = leidenalg.find_partition(
                g,
                leidenalg.RBConfigurationVertexPartition,
                resolution_parameter=resolution,
                weights="weight",
            )

            tier_key = f"C{tier}"
            communities[tier_key] = {}
            for comm_idx, members in enumerate(partition):
                comm_id = f"{tier_key}_{comm_idx}"
                for node_idx in members:
                    uid = nodes[node_idx]
                    communities[tier_key][uid] = comm_id

            tier_counts[tier_key] = len(partition)
            logger.info(
                f"Leiden {tier_key} (resolution={resolution}): "
                f"{len(partition)} 커뮤니티"
            )

        # 4. Neo4j에 커뮤니티 정보 배치 저장 (UNWIND 사용)
        c0_data = communities.get("C0", {})
        if c0_data:
            batch = [{"uid": uid, "comm_id": cid} for uid, cid in c0_data.items()]
            self._client.write(
                "UNWIND $batch AS row "
                "MATCH (n:Entity {uid: row.uid}) "
                "SET n.community_id = row.comm_id, n.community_tier = 0",
                batch=batch,
            )

        # C1~C3도 배치로 저장
        for tier in range(1, 4):
            tier_key = f"C{tier}"
            tier_data = communities.get(tier_key, {})
            if not tier_data:
                continue
            batch = [{"uid": uid, "comm_id": cid} for uid, cid in tier_data.items()]
            # Property name is safe: community_c1, community_c2, community_c3
            self._client.write(
                f"UNWIND $batch AS row "
                f"MATCH (n:Entity {{uid: row.uid}}) "
                f"SET n.community_c{tier} = row.comm_id",
                batch=batch,
            )

        return {
            "communities": communities,
            "tier_counts": tier_counts,
            "node_count": len(nodes),
        }

    def save(self, result: dict[str, Any], output_path: str | Path) -> None:
        """커뮤니티 결과를 JSON으로 저장한다."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # numpy 등 비직렬화 가능 타입 제거
        serializable = {
            "communities": result["communities"],
            "tier_counts": result["tier_counts"],
            "node_count": result.get("node_count", 0),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load(input_path: str | Path) -> dict[str, Any]:
        """저장된 커뮤니티 결과를 로드한다."""
        with open(input_path, encoding="utf-8") as f:
            return json.load(f)
