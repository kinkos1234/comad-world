"""리포트 생성기 — 하이브리드 템플릿+LLM 방식

구조와 데이터 하이라이트는 코드로 확실히 생성하고,
해석/내러티브 부분만 LLM에 맡긴다.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from comad_eye.narration.helpers import clean_name as _clean_name, fmt_pct as _fmt_pct, fmt_score as _fmt_score
from comad_eye.narration.narrative_builder import NarrativeBuilder
from comad_eye.llm_client import LLMClient


class _NoLLMConfigured(Exception):
    """Raised when LLM-dependent code runs without a configured client.
    Wrapped by the per-section try/except so the report degrades
    gracefully (empty strings) instead of timing out."""

logger = logging.getLogger("comadeye")

INTERPRETATION_SYSTEM = """\
시뮬레이션 데이터 해설가. 3~5문장으로 심층 해석을 작성하라.
데이터에 있는 엔티티 이름과 수치만 사용하라.
단순한 데이터 반복이 아니라, 데이터가 의미하는 바를 통찰력 있게 설명하라.
다른 섹션의 분석 결과와 연결되는 시사점이 있으면 언급하라.
의미와 시사점을 자연스러운 한국어로 설명하라.
데이터가 부족하면 부족한 데이터에서도 추론 가능한 시사점을 제시하라.
절대 "시뮬레이션 데이터가 제한적입니다"라는 표현을 쓰지 마라."""

QUOTE_SYSTEM = """\
엔티티 관점의 인용문 생성기.
각 엔티티의 stance 값에 따라 한 문장 인용문을 작성하라.
stance>0.3은 긍정적, stance<-0.3은 부정적, 그 외는 중립적 어조.
주어진 엔티티 이름만 사용하라."""


class ReportGenerator:
    """분석 결과를 마크다운 보고서로 변환한다."""

    def __init__(
        self,
        llm: LLMClient | None = None,
        analysis_dir: str | Path = "data/analysis",
        output_dir: str | Path = "data/reports",
    ):
        # Offline-first: if the caller passes llm=None we DO NOT
        # auto-instantiate a live client. LLM-dependent sections degrade
        # to empty strings instead of timing out on a live network call.
        # Callers that want live inference pass an explicit LLMClient().
        self._llm_provided = llm
        self._analysis_dir = Path(analysis_dir)
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _llm(self) -> LLMClient:
        if self._llm_provided is None:
            raise _NoLLMConfigured
        return self._llm_provided

    def generate(
        self,
        seed_excerpt: str = "",
        metadata: dict[str, Any] | None = None,
        analysis_prompt: str | None = None,
    ) -> Path:
        """리포트를 생성하고 저장한다."""
        self._analysis_prompt = analysis_prompt
        aggregated = self._load_analysis("aggregated")
        causal = self._load_analysis("causal")
        structural = self._load_analysis("structural")
        hierarchy = self._load_analysis("hierarchy")
        temporal = self._load_analysis("temporal")
        recursive = self._load_analysis("recursive")
        cross_space = self._load_analysis("cross_space")

        meta = metadata or {}
        parts: list[str] = []

        # ===== 제목 =====
        title = self._generate_title(seed_excerpt, aggregated)
        subtitle = self._generate_subtitle(aggregated)
        parts.append(f"# {title}\n")
        parts.append(f"> {subtitle}\n")
        parts.append("---\n")

        # ===== 렌즈 인사이트 로드 =====
        lens_insights = self._load_analysis("lens_insights")
        lens_cross = self._load_analysis("lens_cross")

        # ===== NarrativeBuilder 초기화 (LLM 전달 → 서사 보강 활성화) =====
        self._narrator = NarrativeBuilder(
            aggregated=aggregated,
            causal=causal,
            structural=structural,
            hierarchy=hierarchy,
            temporal=temporal,
            recursive=recursive,
            cross_space=cross_space,
            lens_insights=lens_insights,
            lens_cross=lens_cross if isinstance(lens_cross, list) else [],
            llm=self._llm_provided,  # pass-through; NarrativeBuilder handles None
        )

        # ===== 목차 =====
        sections = [
            "Executive Summary",
            "인과 분석",
            "구조 분석",
            "시스템 다이내믹스",
            "교차 분석 인사이트",
        ]
        if lens_insights or lens_cross:
            sections.append("렌즈 딥 분석")
        sections.extend([
            "시나리오 분석",
            "핵심 엔티티 프로파일",
            "리스크 매트릭스",
            "전략적 권고사항",
        ])
        sections.append("부록 A: 추출 온톨로지")
        sections.append("부록 B: 커뮤니티 구조")
        sections.append("부록 C: 시뮬레이션 타임라인")
        sections.append("부록 D: 시뮬레이션 메타데이터")
        parts.append("## 목차\n")
        for i, s in enumerate(sections, 1):
            parts.append(f"{i}. {s}")
        parts.append("")
        parts.append("---\n")

        # ===== 1. Executive Summary =====
        parts.append("## 1. Executive Summary\n")
        if self._analysis_prompt:
            parts.append(f"**분석 주제**: {self._analysis_prompt}\n")
        parts.extend(self._build_executive_summary(aggregated, seed_excerpt))
        parts.append("\n---\n")

        # ===== 2. 인과 분석 =====
        parts.append("## 2. 인과 분석\n")
        parts.append("*분석 근거: **CAUSAL***\n")
        parts.extend(self._build_causal_section(causal, structural))
        parts.append("\n---\n")

        # ===== 3. 구조 분석 =====
        parts.append("## 3. 구조 분석\n")
        parts.append("*분석 근거: **STRUCTURAL** / **HIERARCHY***\n")
        parts.extend(self._build_structural_section(structural, hierarchy))
        parts.append("\n---\n")

        # ===== 4. 시스템 다이내믹스 =====
        parts.append("## 4. 시스템 다이내믹스\n")
        parts.append("*분석 근거: **TEMPORAL** / **RECURSIVE***\n")
        parts.extend(self._build_dynamics_section(temporal, recursive))
        parts.append("\n---\n")

        # ===== 5. 교차 분석 인사이트 =====
        parts.append("## 5. 교차 분석 인사이트\n")
        parts.append("*분석 근거: **CROSS_SPACE***\n")
        parts.extend(self._build_cross_section(cross_space, aggregated))
        parts.append("\n---\n")

        # ===== 6. 렌즈 딥 분석 (조건부) =====
        section_num = 6
        if lens_insights or lens_cross:
            parts.append(f"## {section_num}. 렌즈 딥 분석\n")
            parts.append("*분석 근거: **LENS DEEP FILTERS***\n")
            parts.extend(self._build_lens_section(lens_insights, lens_cross))
            parts.append("\n---\n")
            section_num += 1

        # ===== 시나리오 분석 =====
        parts.append(f"## {section_num}. 시나리오 분석\n")
        parts.append("*분석 근거: **SIMULATION + CAUSAL + RECURSIVE***\n")
        parts.extend(self._narrator.build_scenarios())
        parts.append("\n---\n")
        section_num += 1

        # ===== 핵심 엔티티 프로파일 =====
        parts.append(f"## {section_num}. 핵심 엔티티 프로파일\n")
        parts.append("*분석 근거: **STRUCTURAL + CAUSAL + TEMPORAL***\n")
        parts.extend(self._narrator.build_entity_profiles())
        parts.append("\n---\n")
        section_num += 1

        # ===== 네트워크 진화 요약 =====
        parts.append(f"## {section_num}. 네트워크 진화 요약\n")
        parts.append("*분석 근거: **HIERARCHY + TEMPORAL + SIMULATION***\n")
        parts.extend(self._narrator.build_network_evolution())
        parts.append("\n---\n")
        section_num += 1

        # ===== 리스크 매트릭스 =====
        parts.append(f"## {section_num}. 리스크 매트릭스\n")
        parts.append("*분석 근거: **TALEB LENS + STRUCTURAL HOLES***\n")
        parts.extend(self._narrator.build_risk_matrix())
        parts.append("\n---\n")
        section_num += 1

        # ===== 전략적 권고사항 =====
        parts.append(f"## {section_num}. 전략적 권고사항\n")
        parts.append("*분석 근거: **CAUSAL + STRUCTURAL + LENS CROSS***\n")
        parts.extend(self._narrator.build_recommendations())

        # 렌즈 종합 판단
        lens_synthesis = self._narrator.build_lens_synthesis()
        if lens_synthesis:
            parts.append("### 렌즈 종합 인사이트\n")
            parts.extend(lens_synthesis)

        parts.append("\n---\n")
        section_num += 1

        # ===== 부록 A: 온톨로지 =====
        parts.append(f"## {section_num}. 부록 A: 추출 온톨로지\n")
        parts.extend(self._narrator.build_ontology_appendix())
        parts.append("\n---\n")
        section_num += 1

        # ===== 부록 B: 커뮤니티 구조 =====
        parts.append(f"## {section_num}. 부록 B: 커뮤니티 구조\n")
        parts.extend(self._build_community_appendix(hierarchy))
        parts.append("\n---\n")
        section_num += 1

        # ===== 부록 C: 시뮬레이션 타임라인 =====
        parts.append(f"## {section_num}. 부록 C: 시뮬레이션 타임라인\n")
        parts.extend(self._narrator.build_simulation_timeline())
        parts.append("\n---\n")
        section_num += 1

        # ===== 부록 D: 메타데이터 =====
        parts.append(f"## {section_num}. 부록 D: 시뮬레이션 메타데이터\n")
        parts.extend(self._build_appendix(meta))

        report = "\n".join(parts)
        report = self._post_process(report)

        path = self._output_dir / "report.md"
        path.write_text(report, encoding="utf-8")

        # Quality Gate — 리포트 품질 자동 검증
        issues = self._quality_gate(report)
        if issues:
            logger.warning("리포트 품질 이슈 %d건: %s", len(issues), "; ".join(issues))
        else:
            logger.info("리포트 품질 검증 통과")

        logger.info("리포트 생성 완료: %s", path)
        return path

    # ───────────────────── Title & Subtitle ─────────────────────

    def _generate_title(self, seed: str, agg: dict) -> str:
        """제목을 결정적으로 생성한다 (LLM 호출 절감)."""
        findings = agg.get("key_findings", [])
        if self._analysis_prompt:
            return f"{self._analysis_prompt[:40]} 분석 보고서"
        elif findings:
            return f"{_clean_name(findings[0]['finding'])[:40]} 분석 보고서"
        return "시뮬레이션 분석 보고서"

    def _generate_subtitle(self, agg: dict) -> str:
        """부제를 결정적으로 생성한다 (LLM 호출 절감)."""
        findings = agg.get("key_findings", [])
        spaces = agg.get("spaces", {})
        n_findings = len(findings)
        n_spaces = len(spaces)
        return f"{n_findings}개 핵심 발견, {n_spaces}개 분석공간 시뮬레이션 결과 요약"

    # ───────────────────── Executive Summary ─────────────────────

    def _build_executive_summary(self, agg: dict, seed: str) -> list[str]:
        parts: list[str] = []

        # 시뮬레이션 개요
        sim = agg.get("simulation_summary", {})
        parts.append("### 시뮬레이션 개요\n")
        parts.append(
            f"총 **{sim.get('total_rounds', 'N/A')}라운드**의 시뮬레이션이 수행되었으며, "
            f"**{sim.get('total_meta_edges_fired', 0)}건**의 메타엣지가 발동되었습니다.\n"
        )

        # 핵심 발견
        findings = agg.get("key_findings", [])
        if findings:
            parts.append("### 핵심 발견 (Key Findings)\n")
            parts.append("| 순위 | 발견 내용 | 신뢰도 | 근거 |")
            parts.append("|:----:|----------|:------:|------|")
            for f in findings:
                name = _clean_name(f["finding"])
                conf = _fmt_pct(f.get("confidence", 0))
                spaces = ", ".join(f.get("supporting_spaces", []))
                parts.append(f"| {f['rank']} | {name} | {conf} | {spaces} |")
            parts.append("")

        # 6개 분석공간 요약
        spaces = agg.get("spaces", {})
        if spaces:
            parts.append("### 분석공간 요약\n")
            parts.append("| 분석공간 | 요약 |")
            parts.append("|---------|------|")
            for name, data in spaces.items():
                summary = data.get("summary", "") if isinstance(data, dict) else ""
                parts.append(f"| {name.upper()} | {_clean_name(summary)} |")
            parts.append("")

        # LLM 심층 해석 (Executive Summary 전용 — 더 풍부한 컨텍스트 제공)
        findings_summary = "\n".join(
            f"- {f['finding']} (신뢰도 {f.get('confidence', 0):.0%})"
            for f in findings[:5]
        ) if findings else "없음"

        spaces_summary = "\n".join(
            f"- {name}: {data.get('summary', '')}"
            for name, data in spaces.items()
            if isinstance(data, dict) and data.get("summary")
        ) if spaces else "없음"

        interpretation = self._interpret(
            f"시드 데이터 요약: {seed[:300]}\n"
            f"시뮬레이션: {sim.get('total_rounds')}라운드, "
            f"메타엣지 {sim.get('total_meta_edges_fired', 0)}건 발동\n"
            f"핵심 발견:\n{findings_summary}\n"
            f"분석공간 요약:\n{spaces_summary}",
            question=(
                "이 시뮬레이션의 가장 중요한 시사점 3가지는 무엇인가? "
                "의사결정자가 즉시 주목해야 할 핵심 메시지와, "
                "지금 행동하지 않으면 발생할 위험을 설명하라."
            ),
        )
        if interpretation:
            parts.append("### 종합 해석\n")
            parts.append(f"{interpretation}\n")

        return parts

    # ───────────────────── Causal Section ─────────────────────

    def _build_causal_section(self, causal: dict, structural: dict) -> list[str]:
        parts: list[str] = []

        dag = causal.get("causal_dag", {})
        root_causes = dag.get("root_causes", [])
        terminals = dag.get("terminal_effects", [])

        # DAG 개요
        parts.append("### 인과 그래프 구조\n")
        parts.append(
            f"인과 DAG는 **{dag.get('nodes', 0)}개 노드**, "
            f"**{dag.get('edges', 0)}개 엣지**로 구성됩니다.\n"
        )

        # 근본 원인 테이블
        if root_causes:
            parts.append("### 근본 원인 (Root Causes)\n")
            parts.append("| 엔티티 | 하류 영향 노드 수 |")
            parts.append("|--------|:-----------------:|")
            for rc in root_causes:
                parts.append(
                    f"| {_clean_name(rc['node'])} | {rc['downstream']} |"
                )
            parts.append("")

        # 최종 영향 노드
        if terminals:
            cleaned = [_clean_name(t) for t in terminals]
            parts.append(
                f"**최종 영향 노드**: {', '.join(cleaned)}\n"
            )

        # 인과 체인
        chains = causal.get("causal_chains", [])
        if chains:
            parts.append("### 주요 인과 경로\n")
            for chain in chains:
                path_str = " → ".join(_clean_name(n) for n in chain.get("path", []))
                weight = chain.get("total_weight", 0)
                parts.append(f"- {path_str} *(가중치: {weight:.2f})*")
            parts.append("")

        # 영향 분석
        impact = causal.get("impact_analysis", {})
        if impact:
            parts.append("### 영향도 분석\n")
            parts.append("| 원인 | 가장 큰 영향 | 영향 점수 |")
            parts.append("|------|-------------|:---------:|")
            for entity, data in impact.items():
                affected = _clean_name(data.get("most_affected", ""))
                scores = data.get("impact_scores", {})
                top_score = max(scores.values()) if scores else 0
                parts.append(
                    f"| {_clean_name(entity)} | {affected} | {top_score:.2f} |"
                )
            parts.append("")

        # LLM 해석
        interpretation = self._interpret(
            f"인과 그래프: {dag.get('nodes')}개 노드, {dag.get('edges')}개 엣지\n"
            f"근본 원인: {', '.join(_clean_name(rc['node']) for rc in root_causes)}\n"
            f"최종 영향: {', '.join(_clean_name(t) for t in terminals)}\n"
            f"인과 체인 수: {len(chains)}",
            question=(
                f"근본 원인 '{_clean_name(root_causes[0]['node']) if root_causes else 'N/A'}'가 "
                f"왜 다른 엔티티에 가장 큰 영향을 미치는가? "
                f"이 인과 구조가 시사하는 위험이나 기회는 무엇인가?"
            ),
        )
        if interpretation:
            parts.append(f"{interpretation}\n")

        # 이해관계자 인용문
        quotes = self._generate_quotes(root_causes, "인과 분석의 핵심 원인")
        if quotes:
            parts.append("### 이해관계자 시각\n")
            parts.append(quotes)
            parts.append("")

        return parts

    # ───────────────────── Structural Section ─────────────────────

    def _build_structural_section(self, structural: dict, hierarchy: dict) -> list[str]:
        parts: list[str] = []

        centrality = structural.get("centrality_changes", {})
        nodes = centrality.get("nodes", {})
        top_risers = centrality.get("top_risers", [])

        # 중심성 테이블 — Top 20 (종합 중심성 기준 정렬)
        if nodes:
            sorted_nodes = sorted(
                nodes.items(),
                key=lambda x: (
                    abs(x[1].get("betweenness", 0))
                    + abs(x[1].get("pagerank", 0))
                    + abs(x[1].get("degree", 0))
                ),
                reverse=True,
            )[:20]
            parts.append(f"### 엔티티 중심성 분석 (상위 {len(sorted_nodes)}개)\n")
            parts.append("| 엔티티 | Betweenness | PageRank | Degree |")
            parts.append("|--------|:----------:|:--------:|:------:|")
            for uid, data in sorted_nodes:
                name = data.get("name", _clean_name(uid))
                parts.append(
                    f"| {name} | {_fmt_score(data.get('betweenness', 0))} "
                    f"| {_fmt_score(data.get('pagerank', 0))} "
                    f"| {_fmt_score(data.get('degree', 0))} |"
                )
            if len(nodes) > 20:
                parts.append(f"\n*총 {len(nodes)}개 엔티티 중 상위 20개만 표시*\n")
            parts.append("")

        # 핵심 노드 하이라이트
        if top_risers:
            parts.append("### 핵심 노드 (Top Risers)\n")
            for i, riser in enumerate(top_risers[:5], 1):
                name = riser.get("name", _clean_name(riser.get("node", "")))
                parts.append(
                    f"{i}. **{name}** — "
                    f"Degree: {_fmt_score(riser.get('degree', 0))}, "
                    f"PageRank: {_fmt_score(riser.get('pagerank', 0))}, "
                    f"Betweenness: {_fmt_score(riser.get('betweenness', 0))}"
                )
            parts.append("")

        # 구조적 공백
        holes_raw = structural.get("structural_holes", [])
        hole_count = len(holes_raw) if isinstance(holes_raw, list) else 0
        bridge_raw = structural.get("bridge_nodes", [])
        bridge_count = len(bridge_raw) if isinstance(bridge_raw, list) else 0

        parts.append("### 네트워크 구조 특성\n")
        parts.append(f"- **브릿지 노드**: {bridge_count}개")
        parts.append(f"- **구조적 공백**: {hole_count}개")

        # 브릿지 노드 상세
        if bridge_raw:
            parts.append("")
            parts.append("#### 브릿지 노드 상세\n")
            parts.append("| 노드 | 연결 커뮤니티 수 | 역할 |")
            parts.append("|------|:--------------:|------|")
            for b in bridge_raw[:6]:
                bname = b.get("name", _clean_name(b.get("node", "")))
                n_b = len(b.get("bridges", []))
                role = "핵심 중재자" if n_b >= 3 else "커뮤니티 연결자"
                parts.append(f"| {bname} | {n_b} | {role} |")
        parts.append("")

        # 계층 분석
        tier = hierarchy.get("tier_analysis", {})
        most_dynamic = hierarchy.get("most_dynamic_tier", "N/A")
        if tier:
            parts.append("### 커뮤니티 계층 분석\n")
            parts.append(f"가장 동적인 계층: **{most_dynamic}**\n")
            for tier_name, communities in tier.items():
                if communities:
                    n_comms = len(communities)
                    total_members = sum(
                        c.get("member_count", 0) for c in communities.values()
                    ) if isinstance(communities, dict) else 0
                    parts.append(
                        f"- **{tier_name}**: {n_comms}개 커뮤니티, "
                        f"총 {total_members}명"
                    )
            parts.append("")

        # LLM 해석
        interpretation = self._interpret(
            f"엔티티 수: {len(nodes)}\n"
            f"브릿지 노드: {bridge_count}개\n"
            f"구조적 공백: {len(holes_raw)}개\n"
            f"가장 동적 계층: {most_dynamic}\n"
            f"최고 Degree 노드: {top_risers[0].get('name', '') if top_risers else 'N/A'}",
            question=(
                f"브릿지 노드 {bridge_count}개와 구조적 공백 {len(holes_raw)}개가 "
                f"이 네트워크의 안정성에 어떤 의미를 갖는가? "
                f"브릿지 노드가 제거되면 어떤 일이 발생할 수 있는가?"
            ),
        )
        if interpretation:
            parts.append(f"{interpretation}\n")

        return parts

    # ───────────────────── Dynamics Section ─────────────────────

    def _build_dynamics_section(self, temporal: dict, recursive: dict) -> list[str]:
        parts: list[str] = []

        # 엔티티 생명주기 — 변화가 있는 엔티티만 표시 (최대 20개)
        lifecycle = temporal.get("lifecycle_phases", {})
        if lifecycle:
            # 2개 이상의 고유 단계를 가진 엔티티만 필터링
            dynamic_entities = {}
            static_entities = {}
            for entity, phases in lifecycle.items():
                phase_list = phases if isinstance(phases, list) else [str(phases)]
                unique_phases = list(dict.fromkeys(phase_list))  # 순서 유지 중복 제거
                if len(unique_phases) > 1:
                    dynamic_entities[entity] = unique_phases
                else:
                    static_entities[entity] = unique_phases

            if dynamic_entities:
                # 모든 동적 엔티티가 동일한 패턴인지 확인
                patterns = [" → ".join(p) for p in dynamic_entities.values()]
                unique_patterns = set(patterns)
                if len(unique_patterns) == 1 and len(dynamic_entities) > 5:
                    # 모두 같은 전환 패턴 → 테이블 대신 요약
                    pattern = next(iter(unique_patterns))
                    parts.append("### 엔티티 생명주기\n")
                    parts.append(
                        f"전체 {len(lifecycle)}개 엔티티 중 "
                        f"{len(dynamic_entities)}개가 동일한 전환 패턴 "
                        f"({pattern})을 보였습니다. "
                        f"이는 시뮬레이션 초기에 모든 엔티티가 유사하게 "
                        f"활성화된 후 안정 상태로 수렴했음을 의미합니다.\n"
                    )
                else:
                    parts.append("### 엔티티 생명주기 (변화 감지)\n")
                    parts.append("| 엔티티 | 단계 변화 |")
                    parts.append("|--------|----------|")
                    for entity, phases in list(dynamic_entities.items())[:20]:
                        phase_str = " → ".join(phases)
                        parts.append(f"| {_clean_name(entity)} | {phase_str} |")
                    parts.append("")
            else:
                parts.append("### 엔티티 생명주기\n")
                parts.append(
                    f"전체 {len(lifecycle)}개 엔티티가 동일한 "
                    f"생명주기 패턴을 보였습니다 "
                    f"(대부분 inactive → stable). "
                    f"이는 시뮬레이션 내에서 급격한 상태 전환 없이 "
                    f"안정적으로 수렴했음을 의미합니다.\n"
                )

        # 선행지표
        indicators = temporal.get("leading_indicators", [])
        if indicators:
            parts.append("### 선행지표\n")
            for ind in indicators:
                parts.append(f"- {_clean_name(str(ind))}")
            parts.append("")
        else:
            parts.append("### 선행지표\n")
            parts.append("이번 시뮬레이션에서 유의미한 선행지표는 탐지되지 않았습니다.\n")

        # 피드백 루프
        loops = recursive.get("feedback_loops", [])
        loop_summary = recursive.get("loop_summary", {})
        parts.append("### 피드백 루프 분석\n")
        pos = loop_summary.get("positive_count", 0)
        neg = loop_summary.get("negative_count", 0)
        parts.append(
            f"- 양의 피드백 루프: **{pos}**개\n"
            f"- 음의 피드백 루프: **{neg}**개\n"
        )

        if loops:
            for loop in loops:
                parts.append(f"- {loop}")
        elif pos == 0 and neg == 0:
            parts.append(
                "현재 네트워크에서 피드백 루프가 형성되지 않았으며, "
                "이는 구조적 공백으로 인해 연쇄 반응이 차단된 것으로 해석됩니다.\n"
            )

        # LLM 해석 — 빈 데이터에 맞게 질문 조정
        dynamic_count = len([
            e for e, p in lifecycle.items()
            if isinstance(p, list) and len(set(p)) > 1
        ]) if lifecycle else 0

        if pos == 0 and neg == 0 and dynamic_count == 0:
            interpret_question = (
                "시뮬레이션에서 피드백 루프도 없고 엔티티 상태 변화도 없었다. "
                "이 '정적 수렴' 패턴이 의미하는 바는 무엇인가? "
                "시스템이 실제로 안정적인 것인지, 아니면 시뮬레이션 한계인지 판단하라."
            )
        else:
            interpret_question = (
                f"양의 피드백 루프 {pos}개와 음의 피드백 루프 {neg}개의 "
                f"균형이 시스템의 장기 안정성에 어떤 영향을 미치는가? "
                f"피드백이 적다면 그 원인은 무엇인가?"
            )

        interpretation = self._interpret(
            f"엔티티 생명주기 패턴: 동적 변화 {dynamic_count}개 / 전체 {len(lifecycle)}개\n"
            f"선행지표: {len(indicators)}개\n"
            f"양의 피드백 루프: {pos}개, 음의 피드백 루프: {neg}개",
            question=interpret_question,
        )
        if interpretation:
            parts.append(f"{interpretation}\n")

        return parts

    # ───────────────────── Cross-Space Section ─────────────────────

    def _build_cross_section(self, cross: dict, agg: dict) -> list[str]:
        parts: list[str] = []

        insights = cross.get("cross_insights", [])
        meta_patterns = cross.get("meta_patterns", [])

        if insights:
            parts.append("### 교차 인사이트\n")
            for i, insight in enumerate(insights, 1):
                spaces = ", ".join(insight.get("spaces", []))
                finding = _clean_name(insight.get("finding", ""))
                implication = _clean_name(insight.get("implication", ""))
                conf = _fmt_pct(insight.get("confidence", 0))

                parts.append(f"#### 인사이트 {i}\n")
                parts.append(f"- **발견**: {finding}")
                parts.append(f"- **시사점**: {implication}")
                parts.append(f"- **신뢰도**: {conf}")
                parts.append(f"- **근거 공간**: {spaces}")
                parts.append("")

        if meta_patterns:
            parts.append("### 메타 패턴\n")
            for pattern in meta_patterns:
                parts.append(f"- {_clean_name(str(pattern))}")
            parts.append("")
        else:
            parts.append("### 메타 패턴\n")
            parts.append("이번 시뮬레이션에서 유의미한 메타 패턴은 발견되지 않았습니다.\n")

        # LLM 해석
        interpretation = self._interpret(
            f"교차 인사이트 {len(insights)}개 발견\n"
            + "\n".join(
                f"- {_clean_name(i.get('finding', ''))}: {_clean_name(i.get('implication', ''))}"
                for i in insights
            ),
            question=(
                f"서로 다른 분석공간에서 {len(insights)}개의 교차 인사이트가 발견되었다. "
                f"이 인사이트들이 하나의 일관된 그림을 그리는가, "
                f"아니면 서로 모순되는 신호가 있는가?"
            ),
        )
        if interpretation:
            parts.append(f"{interpretation}\n")

        return parts

    # ───────────────────── Lens Deep Analysis ─────────────────────

    def _build_lens_section(self, lens_insights: dict, lens_cross: list | dict) -> list[str]:
        parts: list[str] = []

        SPACE_NAMES = {
            "hierarchy": "계층공간",
            "temporal": "시간공간",
            "recursive": "재귀공간",
            "structural": "구조공간",
            "causal": "인과공간",
        }

        # 공간별 렌즈 인사이트
        if isinstance(lens_insights, dict) and lens_insights:
            for space_name, insights in lens_insights.items():
                if not isinstance(insights, list) or not insights:
                    continue
                space_label = SPACE_NAMES.get(space_name, space_name.upper())
                parts.append(f"### {space_label} 렌즈 분석\n")

                for ins in insights:
                    lens_name = ins.get("lens_name", ins.get("lens", ""))
                    thinker = ins.get("thinker", "")
                    confidence = ins.get("confidence", 0)

                    parts.append(f"#### {lens_name} ({thinker}) — 신뢰도 {_fmt_pct(confidence)}\n")

                    key_points = ins.get("key_points", [])
                    if key_points:
                        for point in key_points:
                            parts.append(f"- {_clean_name(str(point))}")
                        parts.append("")

                    risk = ins.get("risk_assessment", ins.get("risk", ""))
                    if risk:
                        parts.append(f"**위험 평가**: {_clean_name(str(risk))}\n")

                    opportunity = ins.get("opportunity", "")
                    if opportunity:
                        parts.append(f"**기회 요인**: {_clean_name(str(opportunity))}\n")

        # 렌즈 교차 종합
        cross_list = lens_cross if isinstance(lens_cross, list) else []
        if cross_list:
            parts.append("### 렌즈 교차 종합\n")
            for cross in cross_list:
                lens_name = cross.get("lens_name", "")
                thinker = cross.get("thinker", "")
                spaces = ", ".join(cross.get("spaces", []))
                confidence = cross.get("confidence", 0)

                parts.append(f"#### {lens_name} ({thinker}) 종합 — 신뢰도 {_fmt_pct(confidence)}\n")
                parts.append(f"- **관통 공간**: {spaces}")

                synthesis = cross.get("synthesis", "")
                if synthesis:
                    parts.append(f"- **종합 해석**: {_clean_name(str(synthesis))}")

                pattern = cross.get("cross_pattern", "")
                if pattern:
                    parts.append(f"- **교차 패턴**: {_clean_name(str(pattern))}")

                actionable = cross.get("actionable_insight", "")
                if actionable:
                    parts.append(f"- **핵심 제안**: {_clean_name(str(actionable))}")

                parts.append("")

        return parts

    # ───────────────────── Community Appendix ─────────────────────

    def _build_community_appendix(self, hierarchy: dict) -> list[str]:
        """커뮤니티 구조를 테이블로 정리한다."""
        parts: list[str] = []

        tier = hierarchy.get("tier_analysis", {})
        if not tier:
            parts.append("커뮤니티 구조 데이터가 없습니다.\n")
            return parts

        for tier_name, communities in tier.items():
            if not communities or not isinstance(communities, dict):
                continue
            parts.append(f"### {tier_name}\n")
            parts.append("| 커뮤니티 | 멤버 수 | 평균 Stance | 평균 Volatility | 핵심 멤버 |")
            parts.append("|---------|:------:|:----------:|:--------------:|----------|")
            for comm_id, comm_data in communities.items():
                if not isinstance(comm_data, dict):
                    continue
                members = comm_data.get("member_count", 0)
                avg_stance = comm_data.get("avg_stance", 0)
                avg_vol = comm_data.get("avg_volatility", 0)
                top_members = comm_data.get("top_members", [])
                top_str = ", ".join(
                    _clean_name(m.get("name", m) if isinstance(m, dict) else str(m))
                    for m in top_members[:3]
                )
                parts.append(
                    f"| {_clean_name(str(comm_id))} | {members} | "
                    f"{avg_stance:.2f} | {avg_vol:.2f} | {top_str} |"
                )
            parts.append("")

        return parts

    # ───────────────────── Appendix ─────────────────────

    def _build_appendix(self, meta: dict) -> list[str]:
        parts: list[str] = []
        parts.append("| 항목 | 값 |")
        parts.append("|------|:---:|")
        items = {
            "시뮬레이션 라운드": meta.get("total_rounds", "N/A"),
            "총 이벤트": meta.get("total_events", "N/A"),
            "총 Action 실행": meta.get("total_actions", "N/A"),
            "총 메타엣지 발동": meta.get("total_meta_edges", "N/A"),
            "커뮤니티 재편": meta.get("total_migrations", "N/A"),
        }
        for key, value in items.items():
            parts.append(f"| {key} | **{value}** |")
        parts.append("")
        parts.append("---\n")
        parts.append(
            "*Generated by ComadEye — Ontology-Native Prediction Simulation Engine*"
        )
        return parts

    # ───────────────────── Quality Gate ─────────────────────

    def _quality_gate(self, report: str) -> list[str]:
        """생성된 리포트의 품질을 검증하고 이슈 목록을 반환한다."""
        issues: list[str] = []
        lines = report.split("\n")

        # 1. 필수 섹션 존재 확인
        required_sections = [
            "Executive Summary",
            "인과 분석",
            "구조 분석",
            "시스템 다이내믹스",
            "교차 분석 인사이트",
            "시나리오 분석",
            "핵심 엔티티 프로파일",
            "리스크 매트릭스",
            "전략적 권고사항",
            "부록",
        ]
        for section in required_sections:
            if section not in report:
                issues.append(f"필수 섹션 누락: {section}")

        # 2. 빈 섹션 감지 (섹션 제목 바로 뒤에 다음 섹션이 오는 경우)
        for i, line in enumerate(lines):
            if line.startswith("## ") and i + 1 < len(lines):
                for j in range(i + 1, min(i + 4, len(lines))):
                    stripped = lines[j].strip()
                    if stripped and not stripped.startswith("*분석 근거"):
                        break
                    if stripped.startswith("## "):
                        issues.append(f"빈 섹션: {line.strip()}")
                        break

        # 3. 테이블 깨짐 감지 (| 로 시작하는 줄의 열 수 불일치)
        table_rows: list[tuple[int, int]] = []  # (line_num, col_count)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("|") and stripped.endswith("|"):
                cols = stripped.count("|") - 1
                table_rows.append((i, cols))
            else:
                if len(table_rows) >= 2:
                    header_cols = table_rows[0][1]
                    for row_num, col_count in table_rows[1:]:
                        if col_count != header_cols:
                            issues.append(f"테이블 열 수 불일치 (line {row_num + 1}): 헤더 {header_cols}열, 행 {col_count}열")
                            break
                table_rows = []

        # 4. LLM 환각 아티팩트 감지
        hallucination_patterns = [
            r"```json",            # JSON 코드블록 유출
            r"\"[a-z_]+\":\s*\{",  # JSON 객체 유출
            r"\[object Object\]",  # JS 직렬화 실패
            r"undefined",          # JS undefined 유출
            r"None\b",             # Python None 유출 (문맥 내)
        ]
        for pattern in hallucination_patterns:
            if re.search(pattern, report):
                issues.append(f"LLM 아티팩트 감지: {pattern}")

        # 5. 최소 길이 검증
        if len(report) < 500:
            issues.append(f"리포트 길이 부족: {len(report)}자 (최소 500자)")

        # 6. 반복 문구 감지 — 동일 문장이 2개 이상 섹션에 등장
        section_texts: dict[str, list[str]] = {}
        current_section = ""
        for line in lines:
            if line.startswith("## "):
                current_section = line.strip()
                section_texts[current_section] = []
            elif current_section and line.strip() and len(line.strip()) > 20:
                section_texts[current_section].append(line.strip())

        all_sentences = []
        for section, texts in section_texts.items():
            for text in texts:
                all_sentences.append((section, text))
        seen_sentences: dict[str, str] = {}
        for section, text in all_sentences:
            if text in seen_sentences and seen_sentences[text] != section:
                issues.append(
                    f"반복 문구 감지: '{text[:50]}...' "
                    f"({seen_sentences[text]} ↔ {section})"
                )
                break  # 첫 번째 반복만 보고
            seen_sentences[text] = section

        # 7. 빈 해석 비율 — LLM 해석 실패가 과다하면 경고
        # 해석 존재 판별: 특정 마커 또는 80자 이상의 산문 단락 존재
        section_count = sum(1 for line in lines if line.startswith("## "))
        empty_interp = 0
        for i, line in enumerate(lines):
            if line.startswith("## ") and i + 1 < len(lines):
                section_end = len(lines)
                for j in range(i + 1, len(lines)):
                    if lines[j].startswith("## "):
                        section_end = j
                        break
                section_block = "\n".join(lines[i:section_end])
                # 부록 섹션은 해석 불필요
                if "부록" in line:
                    continue
                # 해석 마커 또는 산문 단락(테이블/리스트가 아닌 80자+ 텍스트)
                has_marker = any(
                    m in section_block
                    for m in ["종합 해석", "이해관계자 시각"]
                )
                paragraphs = section_block.split("\n\n")
                has_prose = any(
                    len(p.strip()) > 80
                    and not p.strip().startswith("|")
                    and not p.strip().startswith("-")
                    and not p.strip().startswith("#")
                    and not p.strip().startswith("*")
                    and not p.strip().startswith(">")
                    for p in paragraphs
                )
                if not has_marker and not has_prose:
                    empty_interp += 1
        main_sections = max(section_count - 4, 1)  # 부록 4개 제외
        if main_sections > 0 and empty_interp / main_sections > 0.6:
            issues.append(
                f"LLM 해석 부족: 본문 {main_sections}개 섹션 중 "
                f"{empty_interp}개에 해석 없음"
            )

        # 8. 데이터-서사 정합성 — "N/A"로만 채워진 데이터 섹션 감지
        na_heavy_sections = []
        current_section = ""
        na_count = 0
        data_count = 0
        for line in lines:
            if line.startswith("## "):
                if current_section and data_count > 0 and na_count / data_count > 0.5:
                    na_heavy_sections.append(current_section)
                current_section = line.strip()
                na_count = 0
                data_count = 0
            elif "N/A" in line or "없습니다" in line or "없음" in line:
                na_count += 1
                data_count += 1
            elif line.strip().startswith("|") or line.strip().startswith("-"):
                data_count += 1
        if current_section and data_count > 0 and na_count / data_count > 0.5:
            na_heavy_sections.append(current_section)
        for section in na_heavy_sections:
            if "부록" not in section:
                issues.append(f"데이터 부족 섹션: {section} (N/A·없음 비율 50% 초과)")

        return issues

    # ───────────────────── LLM Helpers ─────────────────────

    def _interpret(self, data_summary: str, question: str = "") -> str:
        """데이터 요약에 대한 LLM 해석을 3~5문장으로 생성한다.

        refac.md 5.4: LLM에는 분석 결과 전체가 아니라 서술용 digest만 보낸다.
        실패 시 빈 문자열을 반환하여 해당 섹션은 데이터만으로 표시한다.

        Args:
            data_summary: 분석 데이터 요약 텍스트.
            question: 구체적 해석 질문 (빈 문자열이면 범용 해석 요청).
        """
        # digest 축소: 최대 1500자로 제한
        digest = data_summary[:1500] if len(data_summary) > 1500 else data_summary

        system = INTERPRETATION_SYSTEM
        if self._analysis_prompt:
            system += f"\n\n분석 주제: {self._analysis_prompt}\n위 주제와 관련된 관점에서 해석하세요."

        # 구체적 질문이 있으면 범용 "해석하세요" 대신 사용
        if question:
            prompt = f"아래 데이터를 보고 질문에 답하세요.\n\n[데이터]\n{digest}\n\n[질문]\n{question}"
        else:
            prompt = f"아래 데이터를 해석하세요:\n\n{digest}"

        try:
            result = self._llm.generate(
                system=system,
                prompt=prompt,
                task_type="interpretation",
            )
            if result:
                result = self._post_process(result.strip())
            return result or ""
        except Exception as e:
            logger.warning(f"섹션 해석 LLM 실패 (fallback: 데이터만 표시): {e}")
            return ""

    def _generate_quotes(
        self,
        entities: list[dict],
        context: str,
    ) -> str:
        """엔티티 인용문을 생성한다. 실패 시 빈 문자열 반환."""
        if not entities:
            return ""

        entity_info = "\n".join(
            f"- {_clean_name(e.get('node', e.get('name', '')))} "
            f"(stance: {e.get('stance', 0.0):.2f})"
            for e in entities[:6]
        )

        quote_system = QUOTE_SYSTEM
        if self._analysis_prompt:
            quote_system += f"\n\n분석 주제: {self._analysis_prompt}\n인용문은 이 주제와 관련된 관점을 반영하세요."

        try:
            result = self._llm.generate(
                system=quote_system,
                prompt=(
                    f"맥락: {context}\n\n"
                    f"엔티티 목록:\n{entity_info}\n\n"
                    "각 엔티티에 대해 다음 형식으로 인용문을 생성하세요:\n"
                    '> "인용문" — **엔티티명**, 역할'
                ),
                task_type="quote",
            )
            if result:
                result = self._post_process(result.strip())
            return result or ""
        except Exception as e:
            logger.warning(f"인용문 생성 LLM 실패: {e}")
            return ""

    # ───────────────────── Post Processing ─────────────────────

    def _post_process(self, text: str) -> str:
        """LLM 출력에서 JSON 필드명과 기술적 아티팩트를 정리한다."""
        # 한글_한글 패턴의 밑줄을 공백으로 변환 (범용)
        text = re.sub(r"(?<=[\uac00-\ud7a3])_(?=[\uac00-\ud7a3])", " ", text)

        # JSON 키 이름 패턴 제거
        text = re.sub(r"\*\*downstream_count\*\*\s*:", "하류 영향:", text)
        text = re.sub(r"\*\*most_affected\*\*\s*:", "가장 큰 영향:", text)
        text = re.sub(r"\*\*impact_scores\*\*\s*:", "영향 점수:", text)
        text = re.sub(r"downstream_count", "하류 영향 수", text)
        text = re.sub(r"most_affected", "가장 큰 영향", text)
        text = re.sub(r"impact_scores", "영향 점수", text)
        text = re.sub(r"total_impact", "총 영향도", text)
        text = re.sub(r"chain_str", "인과 경로", text)

        # LLM 메타 서술 + 필러 문구 제거
        meta_patterns = [
            r"^해석:\s*\n?",
            r"^요약:\s*\n?",
            r"^결론:\s*\n?",
            r"이 보고서에서는[^.]*\.\s*",
            r"시뮬레이션 분석 결과를 요약하고 있습니다\.\s*",
            r"즉, 시뮬레이션 결과에서 중요한 정보를 간단하게 요약한 것입니다\.\s*",
            r"시뮬레이션 데이터가 제한적입니다\.?\s*",
            r"시뮬레이션 데이터가 제한적이기는 하나,?\s*",
        ]
        for pattern in meta_patterns:
            text = re.sub(pattern, "", text, flags=re.MULTILINE)

        # 연속 빈 줄 정리
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text

    # ───────────────────── File I/O ─────────────────────

    def _load_analysis(self, name: str) -> dict[str, Any]:
        """분석 결과 JSON을 로드한다."""
        path = self._analysis_dir / f"{name}.json"
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)
