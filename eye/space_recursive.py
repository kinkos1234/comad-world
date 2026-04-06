"""재귀공간 분석 — 피드백 루프 탐지 + 프랙탈 패턴"""

from __future__ import annotations

from typing import Any

import networkx as nx

from analysis.base import AnalysisSpace


class RecursiveSpace(AnalysisSpace):
    """자기강화/자기억제 피드백 루프와 프랙탈 패턴을 분석한다."""

    name = "recursive"

    def analyze(self) -> dict[str, Any]:
        graph = self._build_networkx_graph()
        feedback_loops = self._detect_feedback_loops(graph)
        fractal_patterns = self._detect_fractal_patterns()

        return {
            "feedback_loops": feedback_loops,
            "fractal_patterns": fractal_patterns,
            "loop_summary": {
                "positive_count": sum(
                    1 for lbl in feedback_loops if lbl["type"] == "positive"
                ),
                "negative_count": sum(
                    1 for lbl in feedback_loops if lbl["type"] == "negative"
                ),
                "mixed_count": sum(
                    1 for lbl in feedback_loops if lbl["type"] == "mixed"
                ),
            },
        }

    def _build_networkx_graph(self) -> nx.DiGraph:
        """Neo4j 관계를 NetworkX DiGraph로 변환한다."""
        G = nx.DiGraph()

        if not self._data.graph:
            return G

        # 엔티티 노드
        entities = self._data.graph.query(
            "MATCH (n:Entity) RETURN n.uid AS uid, n.name AS name, "
            "n.stance AS stance, n.community_id AS cid"
        )
        for ent in entities or []:
            G.add_node(ent["uid"], **ent)

        # 관계 엣지
        edges = self._data.graph.query(
            "MATCH (a:Entity)-[r]->(b:Entity) "
            "RETURN a.uid AS src, b.uid AS tgt, type(r) AS rel, "
            "r.weight AS weight"
        )
        for edge in edges or []:
            G.add_edge(
                edge["src"],
                edge["tgt"],
                rel_type=edge.get("rel", "UNKNOWN"),
                weight=float(edge.get("weight", 1.0)),
            )

        return G

    def _detect_feedback_loops(
        self, graph: nx.DiGraph
    ) -> list[dict[str, Any]]:
        """사이클을 탐지하고 피드백 루프 유형을 분류한다."""
        loops: list[dict[str, Any]] = []

        try:
            cycles = list(nx.simple_cycles(graph))
        except Exception:
            return loops

        # 길이 2~5인 사이클만
        cycles = [c for c in cycles if 2 <= len(c) <= 5]
        # 최대 20개
        cycles = cycles[:20]

        for cycle in cycles:
            # 사이클 내 각 노드의 stance 변화
            changes = []
            for uid in cycle:
                timeline = self._data.get_entity_timeline(uid)
                stance_deltas = [
                    e.get("delta", 0)
                    for e in timeline
                    if e.get("property") == "stance"
                ]
                total_delta = sum(stance_deltas)
                changes.append(total_delta)

            # 루프 유형 분류
            if not changes:
                loop_type = "mixed"
            elif all(c > 0 for c in changes) or all(c < 0 for c in changes):
                loop_type = "positive"  # 자기강화
            elif self._alternating_signs(changes):
                loop_type = "negative"  # 자기억제
            else:
                loop_type = "mixed"

            # 엣지 관계 유형
            edge_types = []
            for i in range(len(cycle)):
                src = cycle[i]
                tgt = cycle[(i + 1) % len(cycle)]
                edge_data = graph.get_edge_data(src, tgt, default={})
                edge_types.append(edge_data.get("rel_type", "?"))

            strength = (
                sum(abs(c) for c in changes) / len(changes) if changes else 0
            )

            loops.append({
                "nodes": cycle,
                "edges": edge_types,
                "type": loop_type,
                "strength": round(strength, 4),
                "stability": "unstable" if loop_type == "positive" else "stable",
            })

        # 강도 내림차순 정렬
        loops.sort(key=lambda lbl: lbl["strength"], reverse=True)
        return loops

    @staticmethod
    def _alternating_signs(values: list[float]) -> bool:
        """부호가 교대로 바뀌는지 확인한다."""
        if len(values) < 2:
            return False
        for i in range(len(values) - 1):
            if values[i] * values[i + 1] >= 0:
                return False
        return True

    def _detect_fractal_patterns(self) -> list[dict[str, Any]]:
        """동일 패턴이 서로 다른 계층에서 반복되는지 탐지한다."""
        patterns: list[dict[str, Any]] = []

        if not self._data.graph:
            return patterns

        # tier별 변화 패턴 추출
        tier_patterns: dict[int, list[float]] = {}

        for tier in range(4):
            communities = self._data.graph.query(
                "MATCH (n:Entity) WHERE n.community_id IS NOT NULL "
                "AND coalesce(n.community_tier, 0) = $tier "
                "RETURN collect(n.uid) AS members",
                tier=tier,
            )

            if not communities:
                continue

            members = communities[0].get("members", []) if communities else []
            deltas: list[float] = []

            for uid in members:
                timeline = self._data.get_entity_timeline(uid)
                for entry in timeline:
                    if entry.get("property") == "stance":
                        deltas.append(entry.get("delta", 0))

            if deltas:
                tier_patterns[tier] = deltas

        # 인접 tier 간 패턴 유사도 비교
        for tier in range(3):
            if tier not in tier_patterns or (tier + 1) not in tier_patterns:
                continue

            p1 = tier_patterns[tier]
            p2 = tier_patterns[tier + 1]
            similarity = self._pattern_similarity(p1, p2)

            if similarity > 0.6:
                patterns.append({
                    "tiers": [tier, tier + 1],
                    "similarity": round(similarity, 3),
                    "description": (
                        f"C{tier}과 C{tier + 1}에서 유사한 변화 패턴 반복 "
                        f"(유사도 {similarity:.1%})"
                    ),
                })

        return patterns

    @staticmethod
    def _pattern_similarity(a: list[float], b: list[float]) -> float:
        """두 변화 패턴의 유사도를 계산한다."""
        if not a or not b:
            return 0.0

        import numpy as np

        # 정규화
        a_arr = np.array(a)
        b_arr = np.array(b)

        # 히스토그램 비교 (분포 유사도)
        bins = np.linspace(
            min(a_arr.min(), b_arr.min()),
            max(a_arr.max(), b_arr.max()),
            11,
        )
        hist_a, _ = np.histogram(a_arr, bins=bins, density=True)
        hist_b, _ = np.histogram(b_arr, bins=bins, density=True)

        # 코사인 유사도
        dot = np.dot(hist_a, hist_b)
        norm_a = np.linalg.norm(hist_a)
        norm_b = np.linalg.norm(hist_b)

        if norm_a < 1e-10 or norm_b < 1e-10:
            return 0.0

        return float(dot / (norm_a * norm_b))
