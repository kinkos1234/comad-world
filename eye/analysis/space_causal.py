"""인과공간 분석 — 인과 DAG 구축 + Impact Analysis + 근본 원인 식별"""

from __future__ import annotations

from math import prod
from typing import Any

import networkx as nx

from analysis.base import AnalysisSpace


class CausalSpace(AnalysisSpace):
    """인과 관계 구조를 분석한다."""

    name = "causal"

    def analyze(self) -> dict[str, Any]:
        dag = self._build_causal_dag()
        root_causes = self._find_root_causes(dag)
        terminal_effects = self._find_terminal_effects(dag)
        impact = self._impact_analysis(dag, root_causes)
        causal_chains = self._extract_causal_chains(dag, root_causes)

        return {
            "causal_dag": {
                "nodes": dag.number_of_nodes(),
                "edges": dag.number_of_edges(),
                "root_causes": [
                    {"node": n, "downstream": len(list(nx.descendants(dag, n)))}
                    for n in root_causes[:5]
                ],
                "terminal_effects": terminal_effects[:5],
            },
            "impact_analysis": impact,
            "root_cause_ranking": [
                {
                    "node": n,
                    "downstream": len(list(nx.descendants(dag, n))),
                    "total_impact": self._total_impact(dag, n),
                }
                for n in root_causes[:10]
            ],
            "causal_chains": causal_chains,
        }

    def _build_causal_dag(self) -> nx.DiGraph:
        """이벤트-반응-결과의 인과 DAG를 구축한다."""
        dag = nx.DiGraph()

        # 이벤트 → 영향 노드
        for snap in self._data.snapshots:
            changes = snap.get("changes", {})
            round_num = snap.get("round", 0)

            # 이벤트에서 직접 영향
            for event in changes.get("events", []):
                event_uid = event.get("uid", "")
                dag.add_node(event_uid, type="event", round=round_num)

            # 전파 효과
            for prop in changes.get("propagation", []):
                source = prop.get("source", "")
                target = prop.get("target", "")
                delta = abs(prop.get("delta", 0))

                if source and target and source != target:
                    dag.add_node(source, type="entity")
                    dag.add_node(target, type="entity")
                    if dag.has_edge(source, target):
                        old_w = dag[source][target].get("weight", 0)
                        dag[source][target]["weight"] = old_w + delta
                    else:
                        dag.add_edge(
                            source, target,
                            weight=delta,
                            type="propagation",
                            round=round_num,
                        )

            # 메타엣지 발동
            for meta in changes.get("meta_edges", []):
                source = meta.get("source", "")
                target = meta.get("target", "")
                if source and target and source != target:
                    dag.add_edge(
                        source, target,
                        weight=float(meta.get("effect", 0.5)),
                        type="meta_edge",
                        round=round_num,
                    )

            # Action 인과
            for action in changes.get("actions", []):
                actor = action.get("actor", "")
                dag.add_node(actor, type="actor")
                for effect in action.get("effects", []):
                    if not isinstance(effect, dict):
                        continue
                    target = effect.get("target", actor)
                    if target and target != actor:
                        dag.add_edge(
                            actor, target,
                            weight=abs(effect.get("delta", 0.1)),
                            type="action",
                            action=action.get("action", ""),
                            round=round_num,
                        )

        # 사이클 제거 (시간순 방향 유지)
        self._remove_cycles(dag)

        return dag

    def _remove_cycles(self, dag: nx.DiGraph) -> None:
        """시간순으로 사이클을 제거한다."""
        while not nx.is_directed_acyclic_graph(dag):
            try:
                cycle = nx.find_cycle(dag)
                # 가장 약한 엣지 제거
                weakest = min(
                    cycle,
                    key=lambda e: dag[e[0]][e[1]].get("weight", 0),
                )
                dag.remove_edge(weakest[0], weakest[1])
            except nx.NetworkXNoCycle:
                break

    def _find_root_causes(self, dag: nx.DiGraph) -> list[str]:
        """진입 차수 0인 노드 (근본 원인)를 찾는다."""
        roots = [n for n in dag.nodes if dag.in_degree(n) == 0]
        return sorted(
            roots,
            key=lambda n: len(list(nx.descendants(dag, n))),
            reverse=True,
        )

    def _find_terminal_effects(self, dag: nx.DiGraph) -> list[str]:
        """진출 차수 0인 노드 (최종 결과)를 찾는다."""
        terminals = [n for n in dag.nodes if dag.out_degree(n) == 0]
        return sorted(
            terminals,
            key=lambda n: len(list(nx.ancestors(dag, n))),
            reverse=True,
        )

    def _impact_analysis(
        self, dag: nx.DiGraph, root_causes: list[str]
    ) -> dict[str, Any]:
        """각 근본 원인의 하류 영향을 분석한다."""
        results: dict[str, Any] = {}

        for root in root_causes[:5]:
            downstream = list(nx.descendants(dag, root))
            impact_scores: dict[str, float] = {}

            for target in downstream:
                try:
                    paths = list(
                        nx.all_simple_paths(dag, root, target, cutoff=6)
                    )
                    total = 0.0
                    for path in paths[:10]:  # 경로 수 제한
                        weights = [
                            dag[u][v].get("weight", 1.0)
                            for u, v in zip(path, path[1:])
                        ]
                        total += prod(weights)
                    impact_scores[target] = round(total, 4)
                except nx.NetworkXNoPath:
                    continue

            most_affected = (
                max(impact_scores, key=impact_scores.get)
                if impact_scores
                else ""
            )

            results[root] = {
                "downstream_count": len(downstream),
                "most_affected": most_affected,
                "impact_scores": dict(
                    sorted(
                        impact_scores.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:10]
                ),
            }

        return results

    def _total_impact(self, dag: nx.DiGraph, node: str) -> float:
        """노드의 총 하류 영향 점수를 계산한다."""
        total = 0.0
        for target in nx.descendants(dag, node):
            try:
                path = nx.shortest_path(dag, node, target, weight="weight")
                weights = [
                    dag[u][v].get("weight", 1.0)
                    for u, v in zip(path, path[1:])
                ]
                total += prod(weights)
            except nx.NetworkXNoPath:
                continue
        return round(total, 4)

    def _extract_causal_chains(
        self, dag: nx.DiGraph, root_causes: list[str]
    ) -> list[dict[str, Any]]:
        """주요 인과 체인을 추출한다."""
        chains: list[dict[str, Any]] = []

        for root in root_causes[:5]:
            terminals = self._find_terminal_effects(dag)

            for terminal in terminals[:5]:
                try:
                    paths = list(
                        nx.all_simple_paths(dag, root, terminal, cutoff=8)
                    )
                    if not paths:
                        continue

                    # 가장 강한 경로 선택
                    best_path = max(
                        paths[:10],
                        key=lambda p: sum(
                            dag[u][v].get("weight", 0)
                            for u, v in zip(p, p[1:])
                        ),
                    )

                    chains.append({
                        "root": root,
                        "terminal": terminal,
                        "path": best_path,
                        "chain_str": " -> ".join(best_path),
                        "length": len(best_path),
                        "total_weight": round(
                            sum(
                                dag[u][v].get("weight", 0)
                                for u, v in zip(best_path, best_path[1:])
                            ),
                            4,
                        ),
                    })
                except nx.NetworkXNoPath:
                    continue

        chains.sort(key=lambda c: c["total_weight"], reverse=True)
        return chains[:10]
