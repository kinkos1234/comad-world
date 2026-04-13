"""구조공간 분석 — 중심성 변화 + 브릿지 노드 + 구조적 공백"""

from __future__ import annotations

from collections import Counter
from typing import Any

import networkx as nx

from comad_eye.analysis.base import AnalysisSpace


class StructuralSpace(AnalysisSpace):
    """엔티티 간 관계 구조의 변화를 분석한다."""

    name = "structural"

    def analyze(self) -> dict[str, Any]:
        graph = self._build_networkx_graph()

        centrality = self._analyze_centrality(graph)
        bridges = self._find_bridge_nodes(graph)
        holes = self._find_structural_holes(graph)
        edge_dynamics = self._analyze_edge_dynamics()

        return {
            "centrality_changes": centrality,
            "bridge_nodes": bridges,
            "structural_holes": holes,
            "edge_dynamics": edge_dynamics,
        }

    def _build_networkx_graph(self) -> nx.DiGraph:
        """현재 그래프를 NetworkX로 변환한다."""
        G = nx.DiGraph()

        if not self._data.graph:
            return G

        entities = self._data.graph.query(
            "MATCH (n:Entity) RETURN n.uid AS uid, n.name AS name, "
            "n.community_id AS cid, n.stance AS stance, "
            "n.influence_score AS influence"
        )
        for ent in entities or []:
            G.add_node(ent["uid"], **ent)

        edges = self._data.graph.query(
            "MATCH (a:Entity)-[r]->(b:Entity) "
            "RETURN a.uid AS src, b.uid AS tgt, type(r) AS rel, "
            "r.weight AS weight"
        )
        for edge in edges or []:
            G.add_edge(
                edge["src"],
                edge["tgt"],
                rel_type=edge.get("rel", ""),
                weight=float(edge.get("weight", 1.0)),
            )

        return G

    def _analyze_centrality(
        self, graph: nx.DiGraph
    ) -> dict[str, Any]:
        """중심성 지표를 계산한다."""
        if graph.number_of_nodes() == 0:
            return {"nodes": {}, "top_risers": [], "top_fallers": []}

        undirected = graph.to_undirected()

        betweenness = nx.betweenness_centrality(undirected)
        try:
            pagerank = nx.pagerank(graph, max_iter=100)
        except Exception:
            pagerank = {n: 0.0 for n in graph.nodes}
        degree_cent = nx.degree_centrality(undirected)

        nodes: dict[str, dict[str, float]] = {}
        for uid in graph.nodes:
            nodes[uid] = {
                "betweenness": round(betweenness.get(uid, 0), 4),
                "pagerank": round(pagerank.get(uid, 0), 4),
                "degree": round(degree_cent.get(uid, 0), 4),
                "name": graph.nodes[uid].get("name", uid),
            }

        # 상위/하위 정렬
        sorted_by_between = sorted(
            nodes.items(), key=lambda x: x[1]["betweenness"], reverse=True
        )
        top_risers = [
            {"node": uid, **metrics}
            for uid, metrics in sorted_by_between[:5]
        ]
        top_fallers = [
            {"node": uid, **metrics}
            for uid, metrics in sorted_by_between[-5:]
        ]

        return {
            "nodes": nodes,
            "top_risers": top_risers,
            "top_fallers": top_fallers,
        }

    def _find_bridge_nodes(
        self, graph: nx.DiGraph
    ) -> list[dict[str, Any]]:
        """커뮤니티 간 연결 역할을 하는 브릿지 노드를 찾는다."""
        bridges: list[dict[str, Any]] = []

        # 커뮤니티 정보
        community_map: dict[str, str] = {}
        for uid, data in graph.nodes(data=True):
            cid = data.get("cid")
            if cid is not None:
                community_map[uid] = str(cid)

        if not community_map:
            return bridges

        # 각 노드가 연결된 외부 커뮤니티 수
        for uid in graph.nodes:
            my_cid = community_map.get(uid)
            if my_cid is None:
                continue

            external_cids: set[str] = set()
            for neighbor in set(graph.predecessors(uid)) | set(
                graph.successors(uid)
            ):
                n_cid = community_map.get(neighbor)
                if n_cid is not None and n_cid != my_cid:
                    external_cids.add(n_cid)

            if len(external_cids) >= 2:
                bridges.append({
                    "node": uid,
                    "name": graph.nodes[uid].get("name", uid),
                    "own_community": my_cid,
                    "bridges": sorted(external_cids),
                    "bridge_count": len(external_cids),
                })

        bridges.sort(key=lambda b: b["bridge_count"], reverse=True)
        return bridges[:10]

    def _find_structural_holes(
        self, graph: nx.DiGraph
    ) -> list[dict[str, Any]]:
        """구조적 공백 (연결이 약한 커뮤니티 쌍)을 찾는다."""
        holes: list[dict[str, Any]] = []

        # 커뮤니티별 멤버 수집
        community_members: dict[str, list[str]] = {}
        for uid, data in graph.nodes(data=True):
            cid = data.get("cid")
            if cid is not None:
                cid_str = str(cid)
                community_members.setdefault(cid_str, []).append(uid)

        cids = list(community_members.keys())
        if len(cids) < 2:
            return holes

        # 커뮤니티 쌍 간 연결 밀도
        for i, c1 in enumerate(cids):
            for c2 in cids[i + 1:]:
                members_1 = set(community_members[c1])
                members_2 = set(community_members[c2])

                edge_count = 0
                for src in members_1:
                    for tgt in graph.successors(src):
                        if tgt in members_2:
                            edge_count += 1
                for src in members_2:
                    for tgt in graph.successors(src):
                        if tgt in members_1:
                            edge_count += 1

                max_edges = len(members_1) * len(members_2) * 2
                density = edge_count / max_edges if max_edges > 0 else 0

                if density < 0.05:
                    holes.append({
                        "pair": [c1, c2],
                        "density": round(density, 4),
                        "edge_count": edge_count,
                    })

        holes.sort(key=lambda h: h["density"])
        return holes[:10]

    def _analyze_edge_dynamics(self) -> dict[str, Any]:
        """엣지 생성/소멸 패턴을 분석한다."""
        created: Counter = Counter()
        expired: Counter = Counter()

        for snap in self._data.snapshots:
            changes = snap.get("changes", {})

            for action in changes.get("actions", []):
                effects = action.get("effects", [])
                for effect in effects if isinstance(effects, list) else []:
                    if effect.get("type") == "create_edge":
                        created[effect.get("link_type", "UNKNOWN")] += 1
                    elif effect.get("type") == "expire_edge":
                        expired[effect.get("relation", "UNKNOWN")] += 1

            for meta in changes.get("meta_edges", []):
                action_type = meta.get("action", "")
                if action_type == "create_edge":
                    created[meta.get("link_type", "UNKNOWN")] += 1
                elif action_type == "expire_edge":
                    expired[meta.get("relation", "UNKNOWN")] += 1

        all_types = set(created.keys()) | set(expired.keys())
        net_growth = {
            t: created.get(t, 0) - expired.get(t, 0) for t in all_types
        }

        return {
            "edge_creation_rate": dict(created),
            "edge_expiration_rate": dict(expired),
            "net_growth_by_type": net_growth,
        }
