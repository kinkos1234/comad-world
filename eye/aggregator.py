"""6개 분석공간 통합 — 병렬 실행 + 결과 집계 + 렌즈 딥 필터"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from comad_eye.analysis.base import AnalysisSpace, SimulationData
from comad_eye.analysis.lenses import LensEngine, compute_lens_budget
from comad_eye.analysis.space_causal import CausalSpace
from comad_eye.analysis.space_cross import CrossSpace
from comad_eye.analysis.space_hierarchy import HierarchySpace
from comad_eye.analysis.space_recursive import RecursiveSpace
from comad_eye.analysis.space_structural import StructuralSpace
from comad_eye.analysis.space_temporal import TemporalSpace
from comad_eye.llm_client import LLMClient

logger = logging.getLogger("comadeye")


class AnalysisAggregator:
    """6개 분석공간을 실행하고 결과를 통합한다."""

    def __init__(
        self,
        data: SimulationData,
        output_dir: str | Path = "data/analysis",
        llm: LLMClient | None = None,
        selected_lenses: list[str] | None = None,
        seed_text: str = "",
        analysis_prompt: str | None = None,
        settings_override: dict[str, Any] | None = None,
        graph_client: Any = None,
        parallel: bool = True,
    ):
        self._data = data
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._llm = llm
        self._selected_lenses = selected_lenses
        self._seed_text = seed_text
        self._analysis_prompt = analysis_prompt
        self._settings_override = settings_override
        self._graph_client = graph_client
        self._parallel = parallel

    def run_all(self) -> dict[str, Any]:
        """모든 분석공간을 실행하고 통합 결과를 반환한다."""
        logger.info("분석공간 실행 시작")

        # 5개 독립 공간 실행
        spaces_to_run: list[AnalysisSpace] = [
            HierarchySpace(self._data),
            TemporalSpace(self._data),
            RecursiveSpace(self._data),
            StructuralSpace(self._data),
            CausalSpace(self._data),
        ]

        space_results_map: dict[str, dict[str, Any]] = {}

        if self._parallel and len(spaces_to_run) > 1:
            logger.info("분석공간 병렬 실행 (%d개)", len(spaces_to_run))
            with ThreadPoolExecutor(max_workers=len(spaces_to_run)) as pool:
                future_to_space = {
                    pool.submit(space.analyze): space
                    for space in spaces_to_run
                }
                for future in as_completed(future_to_space):
                    space = future_to_space[future]
                    try:
                        result = future.result()
                    except Exception:
                        logger.exception("분석공간 %s 실패 — 빈 결과로 대체", space.name)
                        result = {}
                    space_results_map[space.name] = result
                    self._save_result(space.name, result)
        else:
            for space in spaces_to_run:
                try:
                    result = space.analyze()
                except Exception:
                    logger.exception("분석공간 %s 실패 — 빈 결과로 대체", space.name)
                    result = {}
                space_results_map[space.name] = result
                self._save_result(space.name, result)

        hierarchy = space_results_map["hierarchy"]
        temporal = space_results_map["temporal"]
        recursive = space_results_map["recursive"]
        structural = space_results_map["structural"]
        causal = space_results_map["causal"]

        # 렌즈 딥 필터 적용
        lens_insights: dict[str, list[dict[str, Any]]] = {}
        cross_lens_insights: list[dict[str, Any]] = []

        if self._llm:
            # 렌즈 엔진 생성
            if self._selected_lenses:
                # 사용자가 명시적으로 렌즈를 선택한 경우
                logger.info("렌즈 딥 필터 적용 시작 (수동 선택): %s", self._selected_lenses)
                engine = LensEngine(self._llm, self._selected_lenses, graph_client=self._graph_client)
            else:
                # 기본 활성화된 렌즈 사용 (LLM auto_select 호출 절감)
                from comad_eye.analysis.lenses import DEFAULT_LENS_IDS
                budget = compute_lens_budget(self._settings_override)
                default_ids = DEFAULT_LENS_IDS[:budget]
                logger.info("기본 렌즈 사용 (예산: %d개): %s", budget, default_ids)
                engine = LensEngine(self._llm, default_ids, graph_client=self._graph_client)

            space_results = {
                "hierarchy": hierarchy,
                "temporal": temporal,
                "recursive": recursive,
                "structural": structural,
                "causal": causal,
            }
            lens_insights = engine.apply_to_spaces(space_results)
            self._save_result("lens_insights", lens_insights)

            # 렌즈 교차 종합
            cross_lens_insights = engine.synthesize_cross_lens(lens_insights)
            self._save_result("lens_cross", cross_lens_insights)

            # 활성 렌즈 메타 정보 저장
            self._save_result("lens_meta", {
                "active_lens_ids": engine.active_lens_ids,
                "auto_selected": engine.is_auto_selected,
                "count": len(engine.active_lens_ids),
            })

            logger.info(
                "렌즈 딥 필터 완료: 공간별 인사이트 %d개, 교차 인사이트 %d개",
                sum(len(v) for v in lens_insights.values()),
                len(cross_lens_insights),
            )

        # 다중공간 분석 (5개 결과 교차)
        cross_space = CrossSpace(
            data=self._data,
            hierarchy=hierarchy,
            temporal=temporal,
            recursive=recursive,
            structural=structural,
            causal=causal,
        )
        cross = cross_space.analyze()
        self._save_result(cross_space.name, cross)

        # 통합 결과 생성
        aggregated = self._aggregate(
            hierarchy=hierarchy,
            temporal=temporal,
            recursive=recursive,
            structural=structural,
            causal=causal,
            cross=cross,
            lens_insights=lens_insights,
            cross_lens_insights=cross_lens_insights,
        )
        self._save_result("aggregated", aggregated)

        logger.info("분석공간 실행 완료: %d개 인사이트", len(aggregated.get("key_findings", [])))
        return aggregated

    def _aggregate(self, **space_results: dict[str, Any]) -> dict[str, Any]:
        """6개 공간의 결과를 통합한다."""
        hierarchy = space_results["hierarchy"]
        temporal = space_results["temporal"]
        recursive = space_results["recursive"]
        structural = space_results["structural"]
        causal = space_results["causal"]
        cross = space_results["cross"]
        lens_insights = space_results.get("lens_insights", {})
        cross_lens_insights = space_results.get("cross_lens_insights", [])

        # 시뮬레이션 요약
        sim_summary = {
            "total_rounds": len(self._data.snapshots),
            "total_events": len(self._data.events_log),
            "total_actions": len(self._data.actions_log),
            "total_meta_edges_fired": len(self._data.meta_edges_log),
            "community_migrations": len(self._data.community_migrations),
        }

        # 핵심 발견 통합 (신뢰도 기반 정렬)
        key_findings = self._rank_findings(
            hierarchy, temporal, recursive, structural, causal, cross
        )

        # 공간별 요약
        spaces = {
            "hierarchy": {
                "summary": self._summarize_hierarchy(hierarchy),
                "most_dynamic_tier": hierarchy.get("most_dynamic_tier", ""),
            },
            "temporal": {
                "summary": self._summarize_temporal(temporal),
                "leading_indicator_count": len(
                    temporal.get("leading_indicators", [])
                ),
            },
            "recursive": {
                "summary": self._summarize_recursive(recursive),
                "loop_count": sum(
                    recursive.get("loop_summary", {}).values()
                ),
            },
            "structural": {
                "summary": self._summarize_structural(structural),
                "bridge_count": len(structural.get("bridge_nodes", [])),
            },
            "causal": {
                "summary": self._summarize_causal(causal),
                "root_cause_count": len(
                    causal.get("root_cause_ranking", [])
                ),
            },
            "cross_space": {
                "summary": self._summarize_cross(cross),
                "meta_pattern_count": cross.get("meta_pattern_count", 0),
            },
        }

        # 렌즈 인사이트 통합
        lens_summary: dict[str, Any] = {}
        if lens_insights:
            for space_name, insights in lens_insights.items():
                lens_summary[space_name] = [
                    {
                        "lens": ins.get("lens_name", ""),
                        "thinker": ins.get("thinker", ""),
                        "key_points": ins.get("key_points", []),
                        "risk": ins.get("risk_assessment", ""),
                        "opportunity": ins.get("opportunity", ""),
                        "confidence": ins.get("confidence", 0),
                    }
                    for ins in insights
                ]

        result: dict[str, Any] = {
            "simulation_summary": sim_summary,
            "key_findings": key_findings,
            "spaces": spaces,
        }

        if lens_summary:
            result["lens_insights"] = lens_summary
        if cross_lens_insights:
            result["lens_cross_insights"] = cross_lens_insights

        return result

    def _rank_findings(self, *space_results: dict[str, Any]) -> list[dict[str, Any]]:
        """모든 공간의 인사이트를 신뢰도 기반으로 랭킹한다."""
        findings: list[dict[str, Any]] = []
        rank = 1

        # 인과공간: 근본 원인
        causal = space_results[4]
        for root in causal.get("root_cause_ranking", [])[:3]:
            findings.append({
                "rank": rank,
                "finding": (
                    f"{root['node']}가 인과 DAG의 근본 원인 "
                    f"(하류 영향 {root['downstream']}개 노드)"
                ),
                "supporting_spaces": ["causal", "temporal"],
                "confidence": min(0.95, 0.7 + root.get("total_impact", 0) * 0.1),
            })
            rank += 1

        # 다중공간: 메타 패턴
        cross = space_results[5]
        for pattern in cross.get("meta_patterns", []):
            findings.append({
                "rank": rank,
                "finding": pattern.get("description", ""),
                "supporting_spaces": pattern.get("spaces", []),
                "confidence": pattern.get("leverage_score", 0.5),
            })
            rank += 1

        # 재귀공간: 피드백 루프
        recursive = space_results[2]
        positive_loops = [
            lbl for lbl in recursive.get("feedback_loops", [])
            if lbl.get("type") == "positive"
        ]
        if positive_loops:
            strongest = positive_loops[0]
            findings.append({
                "rank": rank,
                "finding": (
                    f"양의 피드백 루프: "
                    f"{' -> '.join(strongest.get('nodes', [])[:4])} "
                    f"(강도 {strongest.get('strength', 0):.2f})"
                ),
                "supporting_spaces": ["recursive", "temporal"],
                "confidence": min(0.9, 0.6 + strongest.get("strength", 0)),
            })
            rank += 1

        # 구조공간: 브릿지 노드
        structural = space_results[3]
        for bridge in structural.get("bridge_nodes", [])[:2]:
            findings.append({
                "rank": rank,
                "finding": (
                    f"{bridge.get('name', bridge['node'])}가 "
                    f"{len(bridge.get('bridges', []))}개 커뮤니티의 브릿지 노드"
                ),
                "supporting_spaces": ["structural"],
                "confidence": 0.7,
            })
            rank += 1

        # 시간공간: 선행지표
        temporal = space_results[1]
        for indicator in temporal.get("leading_indicators", [])[:2]:
            findings.append({
                "rank": rank,
                "finding": (
                    f"{indicator.get('leader_name', '')}가 "
                    f"{indicator.get('follower_name', '')}의 선행지표 "
                    f"(상관 {indicator.get('correlation', 0):.2f}, "
                    f"시차 {indicator.get('lag_rounds', 0)}라운드)"
                ),
                "supporting_spaces": ["temporal"],
                "confidence": abs(indicator.get("correlation", 0)),
            })
            rank += 1

        # 신뢰도 기반 재정렬
        findings.sort(key=lambda f: f["confidence"], reverse=True)
        for i, f in enumerate(findings):
            f["rank"] = i + 1

        return findings[:15]

    # --- 공간별 요약 생성 ---

    def _summarize_hierarchy(self, result: dict[str, Any]) -> str:
        tier = result.get("most_dynamic_tier", "?")
        comm = result.get("most_dynamic_community", "?")
        return f"{tier} 계층의 {comm} 커뮤니티에서 가장 큰 변화"

    def _summarize_temporal(self, result: dict[str, Any]) -> str:
        n_leaders = len(result.get("leading_indicators", []))
        n_events = len(result.get("event_reactions", {}))
        return f"이벤트 {n_events}개 반응 분석, 선행지표 {n_leaders}개 탐지"

    def _summarize_recursive(self, result: dict[str, Any]) -> str:
        summary = result.get("loop_summary", {})
        pos = summary.get("positive_count", 0)
        neg = summary.get("negative_count", 0)
        return f"양의 피드백 루프 {pos}개, 음의 피드백 루프 {neg}개"

    def _summarize_structural(self, result: dict[str, Any]) -> str:
        bridges = len(result.get("bridge_nodes", []))
        holes = len(result.get("structural_holes", []))
        return f"브릿지 노드 {bridges}개, 구조적 공백 {holes}개"

    def _summarize_causal(self, result: dict[str, Any]) -> str:
        dag = result.get("causal_dag", {})
        roots = len(dag.get("root_causes", []))
        return f"인과 DAG: 노드 {dag.get('nodes', 0)}개, 근본 원인 {roots}개"

    def _summarize_cross(self, result: dict[str, Any]) -> str:
        insights = result.get("insight_count", 0)
        patterns = result.get("meta_pattern_count", 0)
        return f"교차 인사이트 {insights}개, 메타 패턴 {patterns}개"

    def _save_result(self, name: str, result: dict[str, Any]) -> Path:
        path = self._output_dir / f"{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        return path
