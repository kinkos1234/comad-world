"""하이브리드 서사 생성기 — 룰 기반 뼈대 + 선택적 LLM 서사 보강.

저사양 모델에서도 풍부한 보고서를 만들기 위해, 데이터 패턴을
자연어 서술로 변환하는 규칙 기반 빌더. LLM이 제공되면 시나리오와
권고사항에 서사적 해석을 덧붙인다.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from comad_eye.narration.helpers import clean_name as _clean, fmt_pct as _pct, fmt_score

logger = logging.getLogger("comadeye")


def _score(v: float) -> str:
    return fmt_score(v, decimals=3)


class NarrativeBuilder:
    """분석 결과를 구조적 서사 블록으로 변환한다.

    llm이 None이면 100% 룰 기반으로 동작 (기존 동작 유지).
    llm이 제공되면 시나리오·권고 뒤에 1~2문장 서사 보강을 추가한다.
    """

    def __init__(
        self,
        aggregated: dict[str, Any],
        causal: dict[str, Any],
        structural: dict[str, Any],
        hierarchy: dict[str, Any],
        temporal: dict[str, Any],
        recursive: dict[str, Any],
        cross_space: dict[str, Any],
        lens_insights: dict[str, Any] | None = None,
        lens_cross: list[dict[str, Any]] | None = None,
        llm: Any | None = None,
    ):
        self._agg = aggregated
        self._causal = causal
        self._structural = structural
        self._hierarchy = hierarchy
        self._temporal = temporal
        self._recursive = recursive
        self._cross = cross_space
        self._lens = lens_insights or {}
        self._lens_cross = lens_cross or []
        self._llm = llm

    def _narrate(self, skeleton: str, question: str) -> str:
        """룰 기반 뼈대에 LLM 서사를 1~2문장 덧붙인다. 실패 시 빈 문자열."""
        if not self._llm:
            return ""
        try:
            result = self._llm.generate(
                system="분석 보고서의 서사 보강기. 1~2문장으로 핵심 시사점만 서술하라. "
                       "데이터에 근거한 해석만 작성하라.",
                prompt=f"[뼈대]\n{skeleton}\n\n[질문]\n{question}",
                task_type="interpretation",
            )
            return result.strip() if result else ""
        except Exception as e:
            logger.warning(f"서사 보강 실패 (룰 기반으로 계속): {e}")
            return ""

    # ───────────────────── Strategic Recommendations ─────────────────────

    def build_recommendations(self) -> list[str]:
        """인과분석 + 렌즈 인사이트에서 전략적 권고사항을 도출한다."""
        parts: list[str] = []
        recommendations: list[dict[str, str]] = []

        # 1. 근본 원인 기반 권고
        root_causes = self._causal.get("causal_dag", {}).get("root_causes", [])
        for rc in root_causes[:5]:
            node = _clean(rc.get("node", ""))
            downstream = rc.get("downstream", 0)
            if downstream >= 2:
                recommendations.append({
                    "priority": "높음",
                    "type": "근본 원인 관리",
                    "target": node,
                    "action": f"{node}의 변화를 모니터링하세요. "
                              f"이 엔티티는 {downstream}개 하류 노드에 영향을 미치는 "
                              f"근본 원인입니다.",
                    "basis": "인과 분석",
                })

        # 2. 브릿지 노드 기반 권고
        bridges = self._structural.get("bridge_nodes", [])
        for bridge in bridges[:4]:
            name = bridge.get("name", _clean(bridge.get("node", "")))
            n_bridges = len(bridge.get("bridges", []))
            if n_bridges >= 1:
                recommendations.append({
                    "priority": "높음",
                    "type": "구조적 허브 보호",
                    "target": name,
                    "action": f"{name}은(는) {n_bridges}개 커뮤니티를 연결하는 "
                              f"브릿지 노드입니다. 이 노드의 안정성을 확보하는 것이 "
                              f"네트워크 연결성 유지에 핵심적입니다.",
                    "basis": "구조 분석",
                })

        # 3. 피드백 루프 기반 권고
        loops = self._recursive.get("feedback_loops", [])
        positive_loops = [lbl for lbl in loops if lbl.get("type") == "positive"]
        if positive_loops:
            strongest = positive_loops[0]
            nodes = " → ".join(_clean(n) for n in strongest.get("nodes", [])[:4])
            recommendations.append({
                "priority": "중간",
                "type": "피드백 루프 제어",
                "target": nodes,
                "action": f"양의 피드백 루프({nodes})가 감지되었습니다. "
                          f"이 루프는 자기 강화적이므로, 루프 내 핵심 노드에 "
                          f"개입하여 과열을 방지하세요.",
                "basis": "재귀 분석",
            })

        # 4. 렌즈 교차 인사이트 기반 권고
        for cross in self._lens_cross[:4]:
            actionable = cross.get("actionable_insight", "")
            lens_name = cross.get("lens_name", "")
            if actionable:
                recommendations.append({
                    "priority": "중간",
                    "type": f"{lens_name} 렌즈 제안",
                    "target": "",
                    "action": _clean(str(actionable)),
                    "basis": f"{lens_name} 렌즈 교차 분석",
                })

        # 5. 구조적 공백 기반 권고
        holes = self._structural.get("structural_holes", [])
        if holes:
            recommendations.append({
                "priority": "낮음",
                "type": "구조적 공백 활용",
                "target": "",
                "action": f"{len(holes)}개의 구조적 공백이 발견되었습니다. "
                          f"이 공백은 새로운 연결을 만들어 영향력을 확대할 "
                          f"기회이자, 정보 전달이 차단되는 위험 요소입니다.",
                "basis": "구조 분석",
            })

        if not recommendations:
            parts.append("현재 시뮬레이션 데이터에서 유의미한 전략적 권고를 도출하기에 "
                         "데이터가 충분하지 않습니다.\n")
            return parts

        parts.append("| 우선순위 | 유형 | 대상 | 권고 내용 | 근거 |")
        parts.append("|:--------:|------|------|----------|------|")
        for rec in recommendations:
            target = rec["target"][:20] if rec["target"] else "—"
            parts.append(
                f"| {rec['priority']} | {rec['type']} | {target} | "
                f"{rec['action']} | {rec['basis']} |"
            )
        parts.append("")

        # LLM 서사 보강 (권고 종합)
        high_priority = [r for r in recommendations if r["priority"] == "높음"]
        if high_priority:
            skeleton = "\n".join(
                f"- [{r['priority']}] {r['type']}: {r['action'][:60]}"
                for r in high_priority
            )
            narration = self._narrate(
                skeleton,
                "위 높음 우선순위 권고들 중 가장 먼저 실행해야 할 것은 무엇이며 그 이유는?",
            )
            if narration:
                parts.append(f"**우선 실행 판단**: {narration}\n")

        return parts

    # ───────────────────── Risk Matrix ─────────────────────

    def build_risk_matrix(self) -> list[str]:
        """Taleb 렌즈 + 구조적 취약점에서 리스크 매트릭스를 생성한다."""
        parts: list[str] = []
        risks: list[dict[str, Any]] = []

        # 1. 구조적 취약점: 단일 브릿지 노드 의존
        bridges = self._structural.get("bridge_nodes", [])
        for bridge in bridges[:3]:
            name = bridge.get("name", _clean(bridge.get("node", "")))
            n_bridges = len(bridge.get("bridges", []))
            risks.append({
                "risk": f"{name} 브릿지 노드 이탈/변화",
                "impact": "높음" if n_bridges >= 3 else "중간",
                "probability": "중간",
                "category": "구조적 취약점",
            })

        # 2. 인과적 취약점: 단일 근본 원인에 대한 과의존
        root_causes = self._causal.get("causal_dag", {}).get("root_causes", [])
        if root_causes:
            rc = root_causes[0]
            risks.append({
                "risk": f"{_clean(rc['node'])} 의존도 과집중 (하류 {rc['downstream']}개)",
                "impact": "높음",
                "probability": "낮음",
                "category": "인과적 집중",
            })

        # 3. 렌즈 기반 리스크 (Taleb/Kahneman)
        for space_name, insights in self._lens.items():
            if not isinstance(insights, list):
                continue
            for ins in insights:
                risk = ins.get("risk_assessment", ins.get("risk", ""))
                lens_id = ins.get("lens_id", "")
                if risk and lens_id in ("taleb", "kahneman"):
                    risks.append({
                        "risk": _clean(str(risk))[:80],
                        "impact": "중간",
                        "probability": "중간",
                        "category": f"{ins.get('lens_name', '')} 렌즈",
                    })

        # 4. 피드백 루프 리스크
        loops = self._recursive.get("feedback_loops", [])
        positive_count = sum(1 for lbl in loops if lbl.get("type") == "positive")
        if positive_count >= 2:
            risks.append({
                "risk": f"{positive_count}개 양의 피드백 루프에 의한 과열 가능성",
                "impact": "높음",
                "probability": "중간",
                "category": "시스템 역학",
            })

        if not risks:
            parts.append("현재 시뮬레이션에서 유의미한 리스크가 감지되지 않았습니다.\n")
            return parts

        parts.append("| 리스크 | 영향도 | 발생확률 | 분류 |")
        parts.append("|--------|:------:|:--------:|------|")
        for r in risks[:15]:
            parts.append(
                f"| {r['risk']} | {r['impact']} | {r['probability']} | {r['category']} |"
            )
        parts.append("")
        return parts

    # ───────────────────── Scenario Analysis ─────────────────────

    def build_scenarios(self) -> list[str]:
        """시뮬레이션 수렴 패턴과 분석 결과를 기반으로 3가지 시나리오를 도출한다."""
        parts: list[str] = []
        sim = self._agg.get("simulation_summary", {})

        total_rounds = sim.get("total_rounds", 10)
        meta_edges = sim.get("total_meta_edges_fired", 0)
        total_actions = sim.get("total_actions", 0)

        # 시스템 활성도 판단
        activity_level = "high" if (meta_edges + total_actions) > 10 else (
            "medium" if (meta_edges + total_actions) > 3 else "low"
        )

        # 피드백 루프 특성
        loop_summary = self._recursive.get("loop_summary", {})
        pos_loops = loop_summary.get("positive_count", 0)
        neg_loops = loop_summary.get("negative_count", 0)

        # 근본 원인
        root_causes = self._causal.get("causal_dag", {}).get("root_causes", [])
        primary_cause = _clean(root_causes[0]["node"]) if root_causes else "주요 동인"

        # 시나리오 1: 기본 시나리오 (Base Case)
        parts.append("#### 시나리오 1: 기본 경로 (Base Case)\n")
        if activity_level == "low":
            parts.append(
                f"현재 추세가 유지되면, 시스템은 **안정적 균형** 상태를 유지합니다. "
                f"{total_rounds}라운드 동안 {meta_edges}건의 메타엣지만 발동되었으며, "
                f"이는 낮은 상호작용 밀도를 의미합니다.\n"
            )
        else:
            parts.append(
                f"현재 추세가 유지되면, {primary_cause}를 중심으로 한 영향이 "
                f"계속 확산됩니다. {total_rounds}라운드 동안 {meta_edges}건의 메타엣지와 "
                f"{total_actions}건의 Action이 발동되었으며, 이 패턴이 지속될 것입니다.\n"
            )

        # 시나리오 2: 긍정 시나리오 (Upside)
        parts.append("#### 시나리오 2: 긍정 시나리오 (Upside)\n")
        bridges = self._structural.get("bridge_nodes", [])
        if bridges:
            bridge_name = bridges[0].get("name", "브릿지 노드")
            parts.append(
                f"{bridge_name} 등 브릿지 노드의 중재 역할이 강화되어 "
                f"커뮤니티 간 협력이 증가합니다. "
            )
        if neg_loops > 0:
            parts.append(
                f"음의 피드백 루프({neg_loops}개)가 시스템 과열을 자연적으로 "
                f"제어하며 안정적 성장 궤도에 진입합니다.\n"
            )
        else:
            parts.append(
                "새로운 자기 교정 메커니즘이 형성되어 "
                "시스템 안정성이 향상됩니다.\n"
            )

        # 시나리오 3: 부정 시나리오 (Downside)
        parts.append("#### 시나리오 3: 부정 시나리오 (Downside)\n")
        if pos_loops > 0:
            parts.append(
                f"양의 피드백 루프({pos_loops}개)가 통제 불능 상태로 가속되어 "
                f"시스템 과열이 발생합니다. "
            )
        if root_causes:
            parts.append(
                f"{primary_cause}의 영향력이 급격히 변화하면, "
                f"하류 {root_causes[0].get('downstream', 0)}개 노드에 "
                f"연쇄적 충격이 전파됩니다. "
            )
        holes = self._structural.get("structural_holes", [])
        if holes:
            parts.append(
                f"구조적 공백({len(holes)}개)으로 인해 일부 커뮤니티가 "
                f"고립되며 시스템 분열이 발생할 수 있습니다.\n"
            )
        else:
            parts.append(
                "핵심 브릿지 노드의 이탈이 네트워크 분절을 초래할 수 있습니다.\n"
            )

        # LLM 서사 보강 (3개 시나리오 종합)
        skeleton = "\n".join(parts)
        narration = self._narrate(
            skeleton,
            "위 3가지 시나리오 중 가장 가능성이 높은 것은 무엇이며, "
            "의사결정자가 가장 경계해야 할 시나리오는 무엇인가? "
            "1~2문장으로 핵심만 서술하라.",
        )
        if narration:
            parts.append(f"\n**시나리오 종합 판단**: {narration}\n")

        return parts

    # ───────────────────── Key Entity Profiles ─────────────────────

    def build_entity_profiles(self) -> list[str]:
        """Top 10 엔티티의 종합 프로파일을 생성한다."""
        parts: list[str] = []

        # 중심성 데이터에서 Top 엔티티 추출
        centrality = self._structural.get("centrality_changes", {})
        nodes = centrality.get("nodes", {})
        top_risers = centrality.get("top_risers", [])

        if not top_risers and not nodes:
            parts.append("엔티티 프로파일을 생성하기에 충분한 데이터가 없습니다.\n")
            return parts

        # 근본 원인 노드 목록
        root_cause_nodes = {
            rc["node"] for rc in
            self._causal.get("causal_dag", {}).get("root_causes", [])
        }

        # 브릿지 노드 목록
        bridge_nodes = {
            b.get("node", ""): len(b.get("bridges", []))
            for b in self._structural.get("bridge_nodes", [])
        }

        # 선행지표 노드
        leaders = {
            ind.get("leader", ""): ind.get("follower_name", "")
            for ind in self._temporal.get("leading_indicators", [])
        }

        profiles = top_risers[:10] if top_risers else list(nodes.values())[:10]

        for i, entity in enumerate(profiles, 1):
            uid = entity.get("node", entity.get("uid", ""))
            name = entity.get("name", _clean(uid))

            parts.append(f"#### {i}. {name}\n")

            # 기본 속성
            stance = entity.get("stance", 0)
            volatility = entity.get("volatility", 0)
            influence = entity.get("influence_score", entity.get("influence", 0))
            parts.append(
                f"- **기본 속성**: Stance={stance:.2f}, "
                f"Volatility={volatility:.2f}, "
                f"Influence={influence:.2f}"
            )

            # 중심성 지표
            degree = entity.get("degree", 0)
            pagerank = entity.get("pagerank", 0)
            betweenness = entity.get("betweenness", 0)
            parts.append(
                f"- **중심성**: Degree={_score(degree)}, "
                f"PageRank={_score(pagerank)}, "
                f"Betweenness={_score(betweenness)}"
            )

            # 역할 태그
            roles: list[str] = []
            if uid in root_cause_nodes:
                roles.append("근본 원인")
            if uid in bridge_nodes:
                roles.append(f"브릿지 노드 ({bridge_nodes[uid]}개 커뮤니티)")
            if uid in leaders:
                roles.append(f"선행지표 → {_clean(leaders[uid])}")
            if pagerank > 0.1:
                roles.append("높은 영향력")
            if betweenness > 0.1:
                roles.append("정보 중재자")
            if volatility > 0.5:
                roles.append("고변동성")
            if abs(stance) > 0.6:
                roles.append("강한 입장" if stance > 0 else "부정적 입장")

            if roles:
                parts.append(f"- **역할**: {', '.join(roles)}")

            # 종합 평가
            risk_level = "높음" if (volatility > 0.5 or betweenness > 0.1) else (
                "중간" if (volatility > 0.2 or pagerank > 0.05) else "낮음"
            )
            parts.append(f"- **리스크 수준**: {risk_level}")

            # 생명주기
            lifecycle = self._temporal.get("lifecycle_phases", {})
            if uid in lifecycle:
                phases = lifecycle[uid]
                phase_str = " → ".join(phases) if isinstance(phases, list) else str(phases)
                parts.append(f"- **생명주기**: {phase_str}")

            parts.append("")

        return parts

    # ───────────────────── Network Evolution Summary ─────────────────────

    def build_network_evolution(self) -> list[str]:
        """시뮬레이션 전체의 네트워크 진화 과정을 요약한다."""
        parts: list[str] = []
        sim = self._agg.get("simulation_summary", {})
        findings = self._agg.get("key_findings", [])

        total_rounds = sim.get("total_rounds", 0)
        total_events = sim.get("total_events", 0)
        total_meta = sim.get("total_meta_edges_fired", 0)
        total_migrations = sim.get("community_migrations", 0)

        # 시뮬레이션 역학 요약
        parts.append("#### 시뮬레이션 역학 요약\n")
        parts.append(
            f"총 {total_rounds}라운드의 시뮬레이션에서 "
            f"{total_events}개의 외부 이벤트가 발생하고, "
            f"{total_meta}건의 메타엣지가 발동되었습니다. "
            f"커뮤니티 간 이동은 {total_migrations}건 발생했습니다."
        )
        parts.append("")

        # 전파 방향 분석
        direction = self._hierarchy.get("propagation_direction", "mixed")
        dir_map = {
            "top_down": "상위 계층에서 하위 계층으로의 하향식 전파",
            "bottom_up": "하위 계층에서 상위 계층으로의 상향식 전파",
            "mixed": "상하 양방향 혼합 전파",
        }
        parts.append(f"**전파 패턴**: {dir_map.get(direction, direction)}")
        parts.append("")

        # 커뮤니티 역학
        tiers = self._hierarchy.get("tier_dynamics", {})
        if tiers:
            parts.append("#### 계층별 역학\n")
            parts.append("| 계층 | 평균 변동성 | 노드 수 | 특성 |")
            parts.append("|:----:|:----------:|:------:|------|")
            for tier_name, tier_data in tiers.items():
                if isinstance(tier_data, dict):
                    vol = tier_data.get("avg_volatility", 0)
                    count = tier_data.get("node_count", 0)
                    trait = "안정적" if vol < 0.1 else ("변동적" if vol < 0.3 else "격변적")
                    parts.append(f"| {tier_name} | {vol:.3f} | {count} | {trait} |")
            parts.append("")

        # 선행지표 요약
        leaders = self._temporal.get("leading_indicators", [])
        if leaders:
            parts.append("#### 선행-후행 관계 요약\n")
            for ind in leaders[:5]:
                leader = _clean(ind.get("leader_name", ""))
                follower = _clean(ind.get("follower_name", ""))
                corr = ind.get("correlation", 0)
                lag = ind.get("lag_rounds", 0)
                parts.append(
                    f"- **{leader}** → **{follower}**: "
                    f"상관계수 {corr:.2f}, 시차 {lag}라운드"
                )
            parts.append("")

        # 핵심 발견 요약
        if findings:
            parts.append("#### 신뢰도 상위 발견\n")
            for f in findings[:5]:
                conf = f.get("confidence", 0)
                spaces = ", ".join(f.get("supporting_spaces", []))
                parts.append(
                    f"- [{_pct(conf)}] {_clean(f.get('finding', ''))} "
                    f"(근거: {spaces})"
                )
            parts.append("")

        return parts

    # ───────────────────── Multi-Lens Synthesis ─────────────────────

    def build_lens_synthesis(self) -> list[str]:
        """렌즈 교차 인사이트를 종합하여 합의점과 분기점을 식별한다."""
        parts: list[str] = []

        if not self._lens_cross:
            return parts

        # 렌즈별 핵심 키워드 수집
        all_risks: list[str] = []
        all_opportunities: list[str] = []

        for space_name, insights in self._lens.items():
            if not isinstance(insights, list):
                continue
            for ins in insights:
                risk = ins.get("risk_assessment", ins.get("risk", ""))
                opp = ins.get("opportunity", "")
                if risk:
                    all_risks.append(_clean(str(risk)))
                if opp:
                    all_opportunities.append(_clean(str(opp)))

        # 합의점 (2개 이상 렌즈에서 공통 언급)
        if all_risks:
            parts.append("#### 렌즈 간 공통 리스크\n")
            for risk in all_risks[:5]:
                parts.append(f"- {risk}")
            parts.append("")

        if all_opportunities:
            parts.append("#### 렌즈 간 공통 기회\n")
            for opp in all_opportunities[:5]:
                parts.append(f"- {opp}")
            parts.append("")

        # 교차 종합 인사이트
        if self._lens_cross:
            parts.append("#### 렌즈 종합 판단\n")
            for cross in self._lens_cross[:5]:
                lens_name = cross.get("lens_name", "")
                thinker = cross.get("thinker", "")
                synthesis = cross.get("synthesis", "")
                confidence = cross.get("confidence", 0)
                if synthesis:
                    parts.append(
                        f"- **{lens_name}** ({thinker}, 신뢰도 {_pct(confidence)}): "
                        f"{_clean(str(synthesis))}"
                    )
            parts.append("")

        return parts

    # ───────────────────── Ontology Appendix ─────────────────────

    def build_ontology_appendix(self) -> list[str]:
        """추출된 온톨로지(엔티티/관계)를 테이블로 정리한다."""
        parts: list[str] = []
        extraction_dir = Path("data/extraction")

        # 엔티티 테이블
        ontology_file = extraction_dir / "comad_eye.ontology.json"
        entities: list[dict] = []
        relationships: list[dict] = []

        if ontology_file.exists():
            try:
                data = json.loads(ontology_file.read_text(encoding="utf-8"))
                raw_entities = data.get("entities", {})
                # entities can be dict (uid→entity) or list
                if isinstance(raw_entities, dict):
                    entities = list(raw_entities.values())
                else:
                    entities = raw_entities
                relationships = data.get("relationships", [])
            except Exception:
                pass

        if entities:
            max_display = 50
            parts.append("### 엔티티 목록\n")
            parts.append("| # | 이름 | 유형 | 설명 |")
            parts.append("|:-:|------|------|------|")
            for i, e in enumerate(entities[:max_display], 1):
                if isinstance(e, str):
                    parts.append(f"| {i} | {_clean(e)} | — | — |")
                    continue
                name = _clean(e.get("name", e.get("uid", "")))
                etype = e.get("object_type", e.get("type", ""))
                desc = e.get("description", "")
                if isinstance(desc, str):
                    desc = _clean(desc)[:60]
                else:
                    desc = ""
                parts.append(f"| {i} | {name} | {etype} | {desc} |")
            parts.append("")
            if len(entities) > max_display:
                parts.append(f"*총 {len(entities)}개 중 상위 {max_display}개만 표시*\n")
            parts.append(f"총 **{len(entities)}개** 엔티티 추출\n")

        if relationships:
            max_rel_display = 50
            parts.append("### 관계 목록\n")
            parts.append("| # | 출발 | 관계 | 도착 | 강도 |")
            parts.append("|:-:|------|------|------|:----:|")
            displayed = 0
            for i, r in enumerate(relationships, 1):
                if isinstance(r, str):
                    continue
                if displayed >= max_rel_display:
                    break
                src = _clean(r.get("source_uid", r.get("source", "")))
                tgt = _clean(r.get("target_uid", r.get("target", "")))
                rel = r.get("link_type", r.get("relationship_type", ""))
                weight = r.get("weight", r.get("strength", 0))
                w_str = f"{weight:.2f}" if isinstance(weight, (int, float)) else str(weight)
                parts.append(f"| {i} | {src} | {rel} | {tgt} | {w_str} |")
                displayed += 1
            parts.append("")
            if len(relationships) > max_rel_display:
                parts.append(f"*총 {len(relationships)}개 중 상위 {max_rel_display}개만 표시*\n")
            parts.append(f"총 **{len(relationships)}개** 관계 추출\n")

        if not entities and not relationships:
            parts.append("온톨로지 데이터가 없습니다.\n")

        # 엔티티 유형 분포
        if entities:
            type_counts: dict[str, int] = {}
            for e in entities:
                if isinstance(e, str):
                    continue
                etype = e.get("object_type", e.get("type", "기타"))
                type_counts[etype] = type_counts.get(etype, 0) + 1
            if type_counts:
                parts.append("### 엔티티 유형 분포\n")
                parts.append("| 유형 | 개수 | 비율 |")
                parts.append("|------|:----:|:----:|")
                total = sum(type_counts.values())
                for etype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
                    pct = count / total * 100 if total else 0
                    parts.append(f"| {etype} | {count} | {pct:.1f}% |")
                parts.append("")

        # 관계 유형 분포
        if relationships:
            rel_counts: dict[str, int] = {}
            for r in relationships:
                if isinstance(r, str):
                    continue
                rtype = r.get("link_type", r.get("relationship_type", "기타"))
                rel_counts[rtype] = rel_counts.get(rtype, 0) + 1
            if rel_counts:
                parts.append("### 관계 유형 분포\n")
                parts.append("| 관계 유형 | 개수 | 비율 |")
                parts.append("|----------|:----:|:----:|")
                total = sum(rel_counts.values())
                for rtype, count in sorted(rel_counts.items(), key=lambda x: -x[1]):
                    pct = count / total * 100 if total else 0
                    parts.append(f"| {rtype} | {count} | {pct:.1f}% |")
                parts.append("")

        return parts

    # ───────────────────── Simulation Timeline ─────────────────────

    def build_simulation_timeline(self) -> list[str]:
        """시뮬레이션 라운드별 타임라인을 생성한다."""
        parts: list[str] = []
        snapshots_dir = Path("data/snapshots")

        if not snapshots_dir.exists():
            parts.append("스냅샷 데이터가 없습니다.\n")
            return parts

        snapshot_files = sorted(snapshots_dir.glob("round_*.json"))
        if not snapshot_files:
            parts.append("스냅샷 데이터가 없습니다.\n")
            return parts

        parts.append("| 라운드 | 이벤트 | 전파 | 메타엣지 | Action | 주요 변화 |")
        parts.append("|:-----:|:-----:|:----:|:-------:|:------:|----------|")

        for sf in snapshot_files:
            try:
                snap = json.loads(sf.read_text(encoding="utf-8"))
                round_num = snap.get("round", 0)
                changes = snap.get("changes", {})

                events = changes.get("events", [])
                propagations = changes.get("propagation", [])
                meta_edges = changes.get("meta_edges", [])
                actions = changes.get("actions", [])

                # 주요 변화 요약
                highlights: list[str] = []
                if events:
                    top_event = events[0]
                    highlights.append(
                        f"이벤트: {_clean(top_event.get('uid', ''))}"
                    )
                if propagations:
                    top_prop = max(
                        propagations,
                        key=lambda p: abs(p.get("delta", 0)),
                        default={},
                    )
                    src = _clean(top_prop.get("source", ""))
                    tgt = _clean(top_prop.get("target", ""))
                    if src and tgt:
                        highlights.append(f"{src}→{tgt}")
                if actions:
                    top_action = actions[0]
                    highlights.append(
                        f"{_clean(top_action.get('actor', ''))}: "
                        f"{_clean(top_action.get('action', ''))}"
                    )

                summary = "; ".join(highlights[:2]) if highlights else "—"
                parts.append(
                    f"| {round_num} | {len(events)} | "
                    f"{len(propagations)} | {len(meta_edges)} | "
                    f"{len(actions)} | {summary} |"
                )
            except Exception:
                continue

        parts.append("")

        # 라운드별 총계
        total_events = 0
        total_props = 0
        for sf in snapshot_files:
            try:
                snap = json.loads(sf.read_text(encoding="utf-8"))
                changes = snap.get("changes", {})
                total_events += len(changes.get("events", []))
                total_props += len(changes.get("propagation", []))
            except Exception:
                continue
        parts.append(
            f"**총계**: 이벤트 {total_events}건, 전파 {total_props}건, "
            f"{len(snapshot_files)}라운드 완료\n"
        )

        return parts
