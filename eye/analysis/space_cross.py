"""다중공간 분석 — 5개 분석공간의 교차 분석 + 메타 패턴 추출"""

from __future__ import annotations

from typing import Any

from analysis.base import AnalysisSpace, SimulationData


class CrossSpace(AnalysisSpace):
    """5개 분석공간 결과를 교차 분석하여 창발적 인사이트를 도출한다."""

    name = "cross_space"

    def __init__(
        self,
        data: SimulationData,
        hierarchy: dict[str, Any],
        temporal: dict[str, Any],
        recursive: dict[str, Any],
        structural: dict[str, Any],
        causal: dict[str, Any],
    ):
        super().__init__(data)
        self._hierarchy = hierarchy
        self._temporal = temporal
        self._recursive = recursive
        self._structural = structural
        self._causal = causal

    def analyze(self) -> dict[str, Any]:
        insights = []

        insights.extend(self._correlate_hierarchy_temporal())
        insights.extend(self._correlate_structural_causal())
        insights.extend(self._correlate_recursive_temporal())
        insights.extend(self._correlate_hierarchy_causal())
        insights.extend(self._correlate_structural_recursive())

        meta_patterns = self._extract_meta_patterns(insights)

        return {
            "cross_insights": insights,
            "meta_patterns": meta_patterns,
            "insight_count": len(insights),
            "meta_pattern_count": len(meta_patterns),
        }

    def _correlate_hierarchy_temporal(self) -> list[dict[str, Any]]:
        """계층 x 시간: 상위 계층이 먼저 변화하는지 분석."""
        insights: list[dict[str, Any]] = []
        direction = self._hierarchy.get("propagation_direction", "mixed")

        if direction == "top_down":
            insights.append({
                "spaces": ["hierarchy", "temporal"],
                "finding": "거시(C3) 변화가 미시(C0)에 선행",
                "implication": "정책/거시 이벤트가 개별 종목에 탑다운으로 영향",
                "confidence": 0.8,
            })
        elif direction == "bottom_up":
            insights.append({
                "spaces": ["hierarchy", "temporal"],
                "finding": "미시(C0) 변화가 거시(C3)에 선행",
                "implication": "개별 사건이 전체 시스템으로 바텀업 확산",
                "confidence": 0.8,
            })

        # 가장 동적인 tier와 선행지표 비교
        most_dynamic = self._hierarchy.get("most_dynamic_tier", "")
        leaders = self._temporal.get("leading_indicators", [])
        if leaders and most_dynamic:
            insights.append({
                "spaces": ["hierarchy", "temporal"],
                "finding": (
                    f"{most_dynamic} 계층이 가장 동적이며, "
                    f"선행지표 {len(leaders)}개 탐지됨"
                ),
                "implication": "해당 계층의 선행지표 모니터링이 예측에 유효",
                "confidence": 0.6,
            })

        return insights

    def _correlate_structural_causal(self) -> list[dict[str, Any]]:
        """구조 x 인과: 브릿지 노드가 인과 체인의 매개체인지 분석."""
        insights: list[dict[str, Any]] = []

        bridge_nodes = {
            b["node"] for b in self._structural.get("bridge_nodes", [])
        }

        # 인과 체인에서 중간 노드 추출
        causal_chains = self._causal.get("causal_chains", [])
        intermediate_nodes: set[str] = set()
        for chain in causal_chains:
            path = chain.get("path", [])
            if len(path) > 2:
                intermediate_nodes.update(path[1:-1])

        # 교집합
        bridge_intermediates = bridge_nodes & intermediate_nodes
        for node in bridge_intermediates:
            bridge_info = next(
                (b for b in self._structural.get("bridge_nodes", [])
                 if b["node"] == node),
                {},
            )
            insights.append({
                "spaces": ["structural", "causal"],
                "finding": (
                    f"{bridge_info.get('name', node)}가 "
                    f"구조적 브릿지이자 인과적 매개체"
                ),
                "implication": "이 노드의 변화가 섹터 간 영향 전파의 핵심 경로",
                "node": node,
                "confidence": 0.85,
            })

        return insights

    def _correlate_recursive_temporal(self) -> list[dict[str, Any]]:
        """재귀 x 시간: 피드백 루프와 시간 패턴의 상관 분석."""
        insights: list[dict[str, Any]] = []

        loops = self._recursive.get("feedback_loops", [])
        positive_loops = [lbl for lbl in loops if lbl.get("type") == "positive"]
        negative_loops = [lbl for lbl in loops if lbl.get("type") == "negative"]

        # 양의 피드백 루프 노드가 선행지표인지
        leaders = {
            ind["leader"]
            for ind in self._temporal.get("leading_indicators", [])
        }

        for loop in positive_loops:
            loop_nodes = set(loop.get("nodes", []))
            overlap = loop_nodes & leaders
            if overlap:
                insights.append({
                    "spaces": ["recursive", "temporal"],
                    "finding": (
                        f"양의 피드백 루프 내 노드가 선행지표로 작동 "
                        f"({', '.join(overlap)})"
                    ),
                    "implication": "자기강화 루프가 시작되면 조기 감지 가능",
                    "confidence": 0.75,
                })

        if positive_loops and negative_loops:
            insights.append({
                "spaces": ["recursive", "temporal"],
                "finding": (
                    f"양의 피드백 루프 {len(positive_loops)}개, "
                    f"음의 피드백 루프 {len(negative_loops)}개 공존"
                ),
                "implication": "시스템이 자기강화와 자기억제 사이에서 진동 가능",
                "confidence": 0.7,
            })

        return insights

    def _correlate_hierarchy_causal(self) -> list[dict[str, Any]]:
        """계층 x 인과: 인과 체인이 특정 계층에 집중되는지 분석."""
        insights: list[dict[str, Any]] = []

        root_causes = self._causal.get("causal_dag", {}).get("root_causes", [])
        most_dynamic_tier = self._hierarchy.get("most_dynamic_tier", "")

        if root_causes and most_dynamic_tier:
            insights.append({
                "spaces": ["hierarchy", "causal"],
                "finding": (
                    f"근본 원인 {len(root_causes)}개 식별, "
                    f"가장 동적인 계층은 {most_dynamic_tier}"
                ),
                "implication": "인과 체인의 시작점과 영향이 집중되는 계층의 관계",
                "confidence": 0.65,
            })

        return insights

    def _correlate_structural_recursive(self) -> list[dict[str, Any]]:
        """구조 x 재귀: 구조적 공백이 피드백 루프를 차단하는지 분석."""
        insights: list[dict[str, Any]] = []

        holes = self._structural.get("structural_holes", [])
        loops = self._recursive.get("feedback_loops", [])

        if holes and not loops:
            insights.append({
                "spaces": ["structural", "recursive"],
                "finding": "구조적 공백이 피드백 루프 형성을 차단",
                "implication": "분절된 구조가 연쇄 반응을 억제하는 효과",
                "confidence": 0.7,
            })
        elif not holes and loops:
            insights.append({
                "spaces": ["structural", "recursive"],
                "finding": "구조적 공백 없이 피드백 루프가 활발",
                "implication": "긴밀한 연결 구조가 연쇄 반응을 증폭",
                "confidence": 0.7,
            })

        return insights

    def _extract_meta_patterns(
        self, insights: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """단일 공간에서 보이지 않는 메타 패턴을 추출한다."""
        patterns: list[dict[str, Any]] = []

        # 패턴 1: 브릿지-인과-피드백 삼중주
        bridge_causal = [
            i for i in insights
            if set(i.get("spaces", [])) == {"structural", "causal"}
            and "node" in i
        ]
        loop_nodes: set[str] = set()
        for loop in self._recursive.get("feedback_loops", []):
            loop_nodes.update(loop.get("nodes", []))

        for insight in bridge_causal:
            node = insight.get("node", "")
            if node in loop_nodes:
                patterns.append({
                    "name": "bridge_leverage_point",
                    "node": node,
                    "description": (
                        f"{node}는 구조적 브릿지 + 인과 매개 + "
                        f"피드백 루프 노드 (삼중주)"
                    ),
                    "leverage_score": 0.92,
                    "spaces": ["structural", "causal", "recursive"],
                })

        # 패턴 2: 계층-시간 역전
        direction = self._hierarchy.get("propagation_direction", "mixed")
        if direction == "bottom_up":
            patterns.append({
                "name": "hierarchy_temporal_inversion",
                "description": (
                    "하위 계층(C0) 변화가 상위 계층(C2+)보다 먼저 발생 "
                    "(바텀업 창발)"
                ),
                "leverage_score": 0.75,
                "spaces": ["hierarchy", "temporal"],
            })

        # 패턴 3: 인과-재귀 공명
        # root_causes extracted but used only via direct dict access below
        for loop in self._recursive.get("feedback_loops", []):
            if loop.get("type") == "positive":
                loop_start = loop.get("nodes", [None])[0]
                terminals = self._causal.get("causal_dag", {}).get(
                    "terminal_effects", []
                )
                if loop_start in terminals:
                    patterns.append({
                        "name": "causal_recursive_resonance",
                        "description": (
                            f"인과 체인의 종점({loop_start})이 "
                            f"양의 피드백 루프의 시작점 — 자기 증폭 위험"
                        ),
                        "leverage_score": 0.88,
                        "spaces": ["causal", "recursive"],
                    })

        return patterns
