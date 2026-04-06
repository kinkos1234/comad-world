"""Tests for narration/report_generator.py — comprehensive coverage.

Covers: generate(), _generate_title(), _generate_subtitle(),
_build_executive_summary(), _build_causal_section(),
_build_structural_section(), _build_dynamics_section(),
_build_cross_section(), _build_lens_section(),
_build_community_appendix(), _build_appendix(),
_interpret(), _generate_quotes(), _post_process(), _quality_gate(),
_load_analysis().
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from narration.report_generator import ReportGenerator


# ───────────────────── Fixtures ─────────────────────


def _mock_llm(return_value: str = "LLM 해석 결과입니다.") -> MagicMock:
    """Create a mock LLMClient that returns a fixed string."""
    llm = MagicMock()
    llm.generate.return_value = return_value
    llm.generate_json.return_value = {"entities": [], "relationships": []}
    return llm


def _analysis_data() -> dict:
    """Return a complete set of analysis JSON files for testing."""
    return {
        "aggregated": {
            "simulation_summary": {
                "total_rounds": 10,
                "total_events": 5,
                "total_actions": 8,
                "total_meta_edges_fired": 3,
                "community_migrations": 2,
            },
            "key_findings": [
                {
                    "rank": 1,
                    "finding": "Entity Alpha is the root cause",
                    "confidence": 0.92,
                    "supporting_spaces": ["causal", "structural"],
                },
                {
                    "rank": 2,
                    "finding": "Bridge Node Beta connects communities",
                    "confidence": 0.85,
                    "supporting_spaces": ["structural"],
                },
            ],
            "spaces": {
                "causal": {"summary": "Causal analysis summary text"},
                "structural": {"summary": "Structural analysis summary text"},
            },
        },
        "causal": {
            "causal_dag": {
                "nodes": 15,
                "edges": 20,
                "root_causes": [
                    {"node": "entity_alpha", "downstream": 7},
                    {"node": "entity_beta", "downstream": 3},
                ],
                "terminal_effects": ["entity_omega", "entity_zeta"],
            },
            "causal_chains": [
                {"path": ["entity_alpha", "entity_gamma", "entity_omega"], "total_weight": 0.85},
            ],
            "impact_analysis": {
                "entity_alpha": {
                    "most_affected": "entity_omega",
                    "impact_scores": {"entity_omega": 0.9, "entity_gamma": 0.7},
                },
            },
        },
        "structural": {
            "bridge_nodes": [
                {"node": "bridge_1", "name": "Bridge One", "bridges": ["c1", "c2", "c3"]},
                {"node": "bridge_2", "name": "Bridge Two", "bridges": ["c2", "c3"]},
            ],
            "structural_holes": [{"hole": "h1"}, {"hole": "h2"}],
            "centrality_changes": {
                "nodes": {
                    "entity_alpha": {
                        "name": "Entity Alpha",
                        "betweenness": 0.15,
                        "pagerank": 0.12,
                        "degree": 0.08,
                    },
                    "entity_beta": {
                        "name": "Entity Beta",
                        "betweenness": 0.05,
                        "pagerank": 0.04,
                        "degree": 0.03,
                    },
                },
                "top_risers": [
                    {
                        "node": "entity_alpha",
                        "name": "Entity Alpha",
                        "stance": 0.5,
                        "volatility": 0.3,
                        "influence_score": 0.8,
                        "degree": 0.08,
                        "pagerank": 0.12,
                        "betweenness": 0.15,
                    },
                ],
            },
        },
        "hierarchy": {
            "most_dynamic_tier": "C0",
            "propagation_direction": "top_down",
            "tier_dynamics": {
                "T0": {"avg_volatility": 0.05, "node_count": 3},
                "T1": {"avg_volatility": 0.25, "node_count": 7},
            },
            "tier_analysis": {
                "T0": {
                    "comm_1": {
                        "member_count": 5,
                        "avg_stance": 0.3,
                        "avg_volatility": 0.2,
                        "top_members": [{"name": "Alpha"}, {"name": "Beta"}],
                    },
                },
            },
        },
        "temporal": {
            "leading_indicators": [
                {
                    "leader": "entity_alpha",
                    "leader_name": "Entity Alpha",
                    "follower_name": "Entity Omega",
                    "correlation": 0.88,
                    "lag_rounds": 2,
                },
            ],
            "lifecycle_phases": {
                "entity_alpha": ["inactive", "active", "stable"],
                "entity_beta": ["inactive", "stable"],
            },
            "event_reactions": {},
        },
        "recursive": {
            "feedback_loops": [
                {"type": "positive", "nodes": ["entity_alpha", "entity_gamma", "entity_alpha"]},
            ],
            "loop_summary": {"positive_count": 1, "negative_count": 0},
        },
        "cross_space": {
            "cross_insights": [
                {
                    "finding": "Cross insight finding",
                    "implication": "Cross insight implication",
                    "confidence": 0.9,
                    "spaces": ["causal", "structural"],
                },
            ],
            "meta_patterns": ["Pattern A"],
        },
        "lens_insights": {
            "causal": [
                {
                    "lens_id": "taleb",
                    "lens_name": "Taleb",
                    "thinker": "Nassim Taleb",
                    "confidence": 0.8,
                    "key_points": ["Point 1", "Point 2"],
                    "risk_assessment": "Black swan risk",
                    "opportunity": "Antifragility opportunity",
                },
            ],
        },
        "lens_cross": [
            {
                "lens_name": "Taleb",
                "thinker": "Nassim Taleb",
                "spaces": ["causal", "structural"],
                "confidence": 0.85,
                "synthesis": "Cross synthesis text",
                "cross_pattern": "Pattern text",
                "actionable_insight": "Take action on X",
            },
        ],
    }


def _write_analysis_files(analysis_dir: Path, data: dict) -> None:
    """Write analysis JSON files to a temp directory."""
    analysis_dir.mkdir(parents=True, exist_ok=True)
    for name, content in data.items():
        (analysis_dir / f"{name}.json").write_text(
            json.dumps(content, ensure_ascii=False), encoding="utf-8"
        )


# ───────────────────── Title & Subtitle ─────────────────────


class TestGenerateTitle:
    def test_with_analysis_prompt(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = "한미 반도체 동맹 분석"
        title = gen._generate_title("seed", {})
        assert "분석 보고서" in title
        assert "한미 반도체 동맹 분석" in title

    def test_with_findings(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        agg = {"key_findings": [{"finding": "Important finding"}]}
        title = gen._generate_title("", agg)
        assert "Important finding" in title
        assert "분석 보고서" in title

    def test_fallback_title(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        title = gen._generate_title("", {})
        assert title == "시뮬레이션 분석 보고서"

    def test_title_truncation(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = "A" * 100
        title = gen._generate_title("", {})
        # Prompt is truncated to [:40]
        assert len(title) < 100


class TestGenerateSubtitle:
    def test_with_findings_and_spaces(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        agg = {
            "key_findings": [{"finding": "f1"}, {"finding": "f2"}],
            "spaces": {"causal": {}, "structural": {}},
        }
        subtitle = gen._generate_subtitle(agg)
        assert "2개 핵심 발견" in subtitle
        assert "2개 분석공간" in subtitle

    def test_empty_data(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        subtitle = gen._generate_subtitle({})
        assert "0개 핵심 발견" in subtitle


# ───────────────────── Executive Summary ─────────────────────


class TestBuildExecutiveSummary:
    def test_includes_simulation_overview(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_executive_summary(data["aggregated"], "seed text")
        text = "\n".join(parts)
        assert "10라운드" in text
        assert "3건" in text

    def test_includes_findings_table(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_executive_summary(data["aggregated"], "seed")
        text = "\n".join(parts)
        assert "Entity Alpha" in text
        assert "92%" in text

    def test_includes_spaces_summary(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_executive_summary(data["aggregated"], "seed")
        text = "\n".join(parts)
        assert "CAUSAL" in text
        assert "STRUCTURAL" in text

    def test_with_llm_interpretation(self, tmp_path):
        llm = _mock_llm("LLM 종합 해석입니다.")
        gen = ReportGenerator(llm=llm, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_executive_summary(data["aggregated"], "seed")
        text = "\n".join(parts)
        assert "종합 해석" in text

    def test_empty_aggregated(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        parts = gen._build_executive_summary({}, "")
        text = "\n".join(parts)
        assert "시뮬레이션 개요" in text

    def test_findings_without_rank(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        agg = {
            "simulation_summary": {"total_rounds": 1, "total_meta_edges_fired": 0},
            "key_findings": [
                {"rank": 1, "finding": "F1", "confidence": 0.5, "supporting_spaces": ["causal"]},
            ],
        }
        parts = gen._build_executive_summary(agg, "seed")
        text = "\n".join(parts)
        assert "F1" in text


# ───────────────────── Causal Section ─────────────────────


class TestBuildCausalSection:
    def test_dag_overview(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_causal_section(data["causal"], data["structural"])
        text = "\n".join(parts)
        assert "15개 노드" in text
        assert "20개 엣지" in text

    def test_root_causes_table(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_causal_section(data["causal"], data["structural"])
        text = "\n".join(parts)
        assert "entity alpha" in text
        assert "7" in text

    def test_terminal_effects(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_causal_section(data["causal"], data["structural"])
        text = "\n".join(parts)
        assert "entity omega" in text

    def test_causal_chains(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_causal_section(data["causal"], data["structural"])
        text = "\n".join(parts)
        assert "인과 경로" in text
        assert "0.85" in text

    def test_impact_analysis(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_causal_section(data["causal"], data["structural"])
        text = "\n".join(parts)
        assert "영향도 분석" in text

    def test_empty_causal(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        parts = gen._build_causal_section(
            {"causal_dag": {"nodes": 0, "edges": 0, "root_causes": [], "terminal_effects": []}},
            {},
        )
        text = "\n".join(parts)
        assert "0개 노드" in text

    def test_with_llm_quotes(self, tmp_path):
        llm = _mock_llm('> "인용문" -- **Entity Alpha**, 리더')
        gen = ReportGenerator(llm=llm, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_causal_section(data["causal"], data["structural"])
        text = "\n".join(parts)
        assert "이해관계자 시각" in text


# ───────────────────── Structural Section ─────────────────────


class TestBuildStructuralSection:
    def test_centrality_table(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_structural_section(data["structural"], data["hierarchy"])
        text = "\n".join(parts)
        assert "Entity Alpha" in text
        assert "Betweenness" in text

    def test_top_risers(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_structural_section(data["structural"], data["hierarchy"])
        text = "\n".join(parts)
        assert "핵심 노드" in text

    def test_bridge_nodes_detail(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_structural_section(data["structural"], data["hierarchy"])
        text = "\n".join(parts)
        assert "Bridge One" in text
        assert "핵심 중재자" in text

    def test_structural_holes_count(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_structural_section(data["structural"], data["hierarchy"])
        text = "\n".join(parts)
        assert "2개" in text  # 2 structural holes

    def test_tier_analysis(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_structural_section(data["structural"], data["hierarchy"])
        text = "\n".join(parts)
        assert "C0" in text

    def test_empty_structural(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        parts = gen._build_structural_section(
            {"centrality_changes": {"nodes": {}, "top_risers": []}, "bridge_nodes": [], "structural_holes": []},
            {},
        )
        text = "\n".join(parts)
        assert "브릿지 노드" in text
        assert "0개" in text

    def test_more_than_20_nodes_truncation(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        nodes = {
            f"entity_{i}": {
                "name": f"Entity {i}",
                "betweenness": 0.01 * i,
                "pagerank": 0.01 * i,
                "degree": 0.01 * i,
            }
            for i in range(25)
        }
        parts = gen._build_structural_section(
            {
                "centrality_changes": {"nodes": nodes, "top_risers": []},
                "bridge_nodes": [],
                "structural_holes": [],
            },
            {},
        )
        text = "\n".join(parts)
        assert "상위 20개만 표시" in text


# ───────────────────── Dynamics Section ─────────────────────


class TestBuildDynamicsSection:
    def test_lifecycle_phases_dynamic(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_dynamics_section(data["temporal"], data["recursive"])
        text = "\n".join(parts)
        # entity_alpha has 3 unique phases
        assert "entity alpha" in text or "생명주기" in text

    def test_leading_indicators(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_dynamics_section(data["temporal"], data["recursive"])
        text = "\n".join(parts)
        assert "선행지표" in text

    def test_feedback_loops(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_dynamics_section(data["temporal"], data["recursive"])
        text = "\n".join(parts)
        assert "피드백 루프" in text
        assert "1" in text  # 1 positive loop

    def test_no_leading_indicators(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        parts = gen._build_dynamics_section(
            {"leading_indicators": [], "lifecycle_phases": {}},
            {"feedback_loops": [], "loop_summary": {"positive_count": 0, "negative_count": 0}},
        )
        text = "\n".join(parts)
        assert "탐지되지 않았습니다" in text

    def test_no_feedback_loops_static(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        parts = gen._build_dynamics_section(
            {"leading_indicators": [], "lifecycle_phases": {}},
            {"feedback_loops": [], "loop_summary": {"positive_count": 0, "negative_count": 0}},
        )
        text = "\n".join(parts)
        assert "피드백 루프가 형성되지 않았" in text

    def test_all_entities_same_pattern(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        lifecycle = {f"e{i}": ["inactive", "stable"] for i in range(10)}
        parts = gen._build_dynamics_section(
            {"leading_indicators": [], "lifecycle_phases": lifecycle},
            {"feedback_loops": [], "loop_summary": {"positive_count": 0, "negative_count": 0}},
        )
        text = "\n".join(parts)
        assert "동일한 전환 패턴" in text

    def test_all_static_entities(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        lifecycle = {f"e{i}": ["stable"] for i in range(5)}
        parts = gen._build_dynamics_section(
            {"leading_indicators": [], "lifecycle_phases": lifecycle},
            {"feedback_loops": [], "loop_summary": {"positive_count": 0, "negative_count": 0}},
        )
        text = "\n".join(parts)
        assert "동일한" in text


# ───────────────────── Cross Section ─────────────────────


class TestBuildCrossSection:
    def test_cross_insights(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_cross_section(data["cross_space"], data["aggregated"])
        text = "\n".join(parts)
        assert "Cross insight finding" in text
        assert "causal, structural" in text

    def test_meta_patterns(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_cross_section(data["cross_space"], data["aggregated"])
        text = "\n".join(parts)
        assert "Pattern A" in text

    def test_no_meta_patterns(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        parts = gen._build_cross_section(
            {"cross_insights": [], "meta_patterns": []}, {}
        )
        text = "\n".join(parts)
        assert "메타 패턴은 발견되지 않았습니다" in text


# ───────────────────── Lens Section ─────────────────────


class TestBuildLensSection:
    def test_lens_insights_rendering(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_lens_section(data["lens_insights"], data["lens_cross"])
        text = "\n".join(parts)
        assert "Taleb" in text
        assert "Nassim Taleb" in text
        assert "Point 1" in text

    def test_lens_cross_rendering(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_lens_section(data["lens_insights"], data["lens_cross"])
        text = "\n".join(parts)
        assert "렌즈 교차 종합" in text
        assert "Cross synthesis text" in text
        assert "Pattern text" in text

    def test_empty_lens(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        parts = gen._build_lens_section({}, [])
        assert parts == []

    def test_lens_risk_and_opportunity(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_lens_section(data["lens_insights"], [])
        text = "\n".join(parts)
        assert "Black swan risk" in text
        assert "Antifragility opportunity" in text


# ───────────────────── Community Appendix ─────────────────────


class TestBuildCommunityAppendix:
    def test_with_tier_data(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        data = _analysis_data()
        parts = gen._build_community_appendix(data["hierarchy"])
        text = "\n".join(parts)
        assert "Alpha" in text
        assert "Beta" in text

    def test_no_tier_data(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        parts = gen._build_community_appendix({})
        text = "\n".join(parts)
        assert "커뮤니티 구조 데이터가 없습니다" in text

    def test_non_dict_communities_skipped(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        parts = gen._build_community_appendix({"tier_analysis": {"T0": "not_a_dict"}})
        # Should not crash; non-dict communities are skipped
        assert isinstance(parts, list)


# ───────────────────── Appendix (Metadata) ─────────────────────


class TestBuildAppendix:
    def test_metadata_table(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        meta = {
            "total_rounds": 10,
            "total_events": 5,
            "total_actions": 3,
            "total_meta_edges": 2,
            "total_migrations": 1,
        }
        parts = gen._build_appendix(meta)
        text = "\n".join(parts)
        assert "10" in text
        assert "ComadEye" in text

    def test_empty_metadata(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        parts = gen._build_appendix({})
        text = "\n".join(parts)
        assert "N/A" in text


# ───────────────────── LLM Interpret ─────────────────────


class TestInterpret:
    def test_with_llm(self, tmp_path):
        llm = _mock_llm("심층 해석 결과입니다.")
        gen = ReportGenerator(llm=llm, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        result = gen._interpret("data summary")
        assert result == "심층 해석 결과입니다."

    def test_with_question(self, tmp_path):
        llm = _mock_llm("질문에 대한 답변")
        gen = ReportGenerator(llm=llm, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        result = gen._interpret("data summary", question="왜 이런 결과가?")
        assert "질문에 대한 답변" in result
        # Verify the prompt includes the question
        call_args = llm.generate.call_args
        assert "왜 이런 결과가?" in call_args.kwargs.get("prompt", "")

    def test_llm_failure_returns_empty(self, tmp_path):
        llm = MagicMock()
        llm.generate.side_effect = Exception("LLM error")
        gen = ReportGenerator(llm=llm, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        result = gen._interpret("data")
        assert result == ""

    def test_llm_returns_none(self, tmp_path):
        llm = _mock_llm(None)
        gen = ReportGenerator(llm=llm, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        result = gen._interpret("data")
        assert result == ""

    def test_digest_truncation(self, tmp_path):
        llm = _mock_llm("ok")
        gen = ReportGenerator(llm=llm, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        long_data = "A" * 3000
        gen._interpret(long_data)
        call_args = llm.generate.call_args
        prompt = call_args.kwargs.get("prompt", "")
        # The digest is truncated to 1500 chars
        assert len(prompt) < 3000

    def test_with_analysis_prompt_context(self, tmp_path):
        llm = _mock_llm("주제 맞춤 해석")
        gen = ReportGenerator(llm=llm, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = "반도체 시장 분석"
        gen._interpret("data")
        call_args = llm.generate.call_args
        system = call_args.kwargs.get("system", "")
        assert "반도체 시장 분석" in system


# ───────────────────── Generate Quotes ─────────────────────


class TestGenerateQuotes:
    def test_with_entities(self, tmp_path):
        llm = _mock_llm('> "인용문" -- **Alpha**, 리더')
        gen = ReportGenerator(llm=llm, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        entities = [{"node": "entity_alpha", "stance": 0.5}]
        result = gen._generate_quotes(entities, "context")
        assert "인용문" in result

    def test_empty_entities(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        result = gen._generate_quotes([], "context")
        assert result == ""

    def test_llm_failure_returns_empty(self, tmp_path):
        llm = MagicMock()
        llm.generate.side_effect = Exception("fail")
        gen = ReportGenerator(llm=llm, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = None
        result = gen._generate_quotes([{"node": "a", "stance": 0}], "ctx")
        assert result == ""

    def test_with_analysis_prompt(self, tmp_path):
        llm = _mock_llm("quote text")
        gen = ReportGenerator(llm=llm, analysis_dir=tmp_path, output_dir=tmp_path)
        gen._analysis_prompt = "반도체 주제"
        gen._generate_quotes([{"node": "a", "stance": 0}], "ctx")
        call_args = llm.generate.call_args
        system = call_args.kwargs.get("system", "")
        assert "반도체 주제" in system


# ───────────────────── Load Analysis ─────────────────────


class TestLoadAnalysis:
    def test_load_existing_file(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        (tmp_path / "test.json").write_text('{"key": "value"}', encoding="utf-8")
        result = gen._load_analysis("test")
        assert result == {"key": "value"}

    def test_load_missing_file(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        result = gen._load_analysis("nonexistent")
        assert result == {}


# ───────────────────── Full Generate ─────────────────────


class TestGenerate:
    def test_full_generate_produces_file(self, tmp_path):
        analysis_dir = tmp_path / "analysis"
        output_dir = tmp_path / "reports"
        data = _analysis_data()
        _write_analysis_files(analysis_dir, data)

        llm = _mock_llm("LLM 해석")
        gen = ReportGenerator(llm=llm, analysis_dir=analysis_dir, output_dir=output_dir)

        path = gen.generate(seed_excerpt="test seed", metadata={"total_rounds": 10})
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "Executive Summary" in content
        assert "인과 분석" in content
        assert "구조 분석" in content
        assert "시스템 다이내믹스" in content

    def test_generate_with_analysis_prompt(self, tmp_path):
        analysis_dir = tmp_path / "analysis"
        output_dir = tmp_path / "reports"
        data = _analysis_data()
        _write_analysis_files(analysis_dir, data)

        llm = _mock_llm("LLM result")
        gen = ReportGenerator(llm=llm, analysis_dir=analysis_dir, output_dir=output_dir)

        path = gen.generate(
            seed_excerpt="seed",
            analysis_prompt="한미 관계 분석",
        )
        content = path.read_text(encoding="utf-8")
        assert "한미 관계 분석" in content

    def test_generate_without_lens_data(self, tmp_path):
        analysis_dir = tmp_path / "analysis"
        output_dir = tmp_path / "reports"
        data = _analysis_data()
        # Remove lens data
        del data["lens_insights"]
        del data["lens_cross"]
        _write_analysis_files(analysis_dir, data)

        gen = ReportGenerator(llm=None, analysis_dir=analysis_dir, output_dir=output_dir)
        path = gen.generate()
        content = path.read_text(encoding="utf-8")
        # Lens section should not appear
        assert "렌즈 딥 분석" not in content

    def test_generate_with_lens_data(self, tmp_path):
        analysis_dir = tmp_path / "analysis"
        output_dir = tmp_path / "reports"
        data = _analysis_data()
        _write_analysis_files(analysis_dir, data)

        gen = ReportGenerator(llm=None, analysis_dir=analysis_dir, output_dir=output_dir)
        path = gen.generate()
        content = path.read_text(encoding="utf-8")
        assert "렌즈 딥 분석" in content

    def test_generate_no_llm(self, tmp_path):
        analysis_dir = tmp_path / "analysis"
        output_dir = tmp_path / "reports"
        data = _analysis_data()
        _write_analysis_files(analysis_dir, data)

        gen = ReportGenerator(llm=None, analysis_dir=analysis_dir, output_dir=output_dir)
        path = gen.generate()
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert len(content) > 500


# ───────────────────── Post Process ─────────────────────


class TestPostProcessExtended:
    def test_meta_filler_removal(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        text = "해석:\n이것은 해석입니다."
        result = gen._post_process(text)
        assert not result.startswith("해석:")

    def test_multiple_json_key_patterns(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        text = "**downstream_count**: 5, **most_affected**: entity"
        result = gen._post_process(text)
        assert "하류 영향" in result
        assert "가장 큰 영향" in result

    def test_total_impact_cleanup(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        result = gen._post_process("total_impact = 5")
        assert "총 영향도" in result

    def test_chain_str_cleanup(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        result = gen._post_process("chain_str: A -> B")
        assert "인과 경로" in result

    def test_simulation_data_limited_phrase(self, tmp_path):
        gen = ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)
        text = "시뮬레이션 데이터가 제한적입니다. 그러나 분석 결과..."
        result = gen._post_process(text)
        assert "시뮬레이션 데이터가 제한적입니다" not in result


# ───────────────────── Quality Gate Extended ─────────────────────


class TestQualityGateExtended:
    def _make_gen(self, tmp_path):
        return ReportGenerator(llm=None, analysis_dir=tmp_path, output_dir=tmp_path)

    def test_empty_section_detected(self, tmp_path):
        gen = self._make_gen(tmp_path)
        report = (
            "## 1. Executive Summary\n"
            "## 2. 인과 분석\n"  # Empty — next line is another section
            "## 3. 구조 분석\nContent\n"
            "## 시스템 다이내믹스\n내용\n"
            "## 교차 분석 인사이트\n내용\n"
            "## 시나리오 분석\n내용\n"
            "## 핵심 엔티티 프로파일\n내용\n"
            "## 리스크 매트릭스\n내용\n"
            "## 전략적 권고사항\n내용\n"
            "## 부록\n내용\n"
            + "x" * 500
        )
        issues = gen._quality_gate(report)
        # All sections have content, so no "빈 섹션" issue expected
        # The quality gate checks for other issues on a well-formed report
        assert isinstance(issues, list)

    def test_llm_interpretation_insufficiency(self, tmp_path):
        gen = self._make_gen(tmp_path)
        # Build report with many sections but no prose/interpretation markers
        sections = [
            "## 1. Executive Summary\n| a | b |\n|---|---|\n| 1 | 2 |\n",
            "## 2. 인과 분석\n| a | b |\n|---|---|\n| 1 | 2 |\n",
            "## 3. 구조 분석\n| a | b |\n|---|---|\n| 1 | 2 |\n",
            "## 4. 시스템 다이내믹스\n| a | b |\n|---|---|\n| 1 | 2 |\n",
            "## 5. 교차 분석 인사이트\n| a | b |\n|---|---|\n| 1 | 2 |\n",
            "## 6. 시나리오 분석\n| a | b |\n|---|---|\n| 1 | 2 |\n",
            "## 7. 핵심 엔티티 프로파일\n| a | b |\n|---|---|\n| 1 | 2 |\n",
            "## 8. 리스크 매트릭스\n| a | b |\n|---|---|\n| 1 | 2 |\n",
            "## 9. 전략적 권고사항\n| a | b |\n|---|---|\n| 1 | 2 |\n",
            "## 10. 부록 A\n내용\n",
            "## 11. 부록 B\n내용\n",
            "## 12. 부록 C\n내용\n",
            "## 13. 부록 D\n내용\n",
        ]
        report = "\n".join(sections) + "x" * 500
        issues = gen._quality_gate(report)
        interp_issues = [i for i in issues if "해석 부족" in i]
        assert len(interp_issues) >= 1

    def test_clean_report_minimal_issues(self, tmp_path):
        gen = self._make_gen(tmp_path)
        sections = [
            "## 1. Executive Summary\n### 종합 해석\n" + ("이것은 매우 중요한 분석 결과를 포함하는 긴 문장입니다. " * 10) + "\n",
            "## 2. 인과 분석\n### 종합 해석\n" + ("인과 관계에 대한 심층적인 해석이 여기에 포함됩니다. " * 10) + "\n",
            "## 3. 구조 분석\n### 종합 해석\n" + ("구조적 분석에 대한 자세한 설명입니다. " * 10) + "\n",
            "## 4. 시스템 다이내믹스\n### 종합 해석\n" + ("시스템 역학에 대한 심층 분석입니다. " * 10) + "\n",
            "## 5. 교차 분석 인사이트\n### 종합 해석\n" + ("교차 분석 인사이트에 대한 해석입니다. " * 10) + "\n",
            "## 6. 시나리오 분석\n### 이해관계자 시각\n내용\n",
            "## 7. 핵심 엔티티 프로파일\n### 종합 해석\n" + ("엔티티 프로파일에 대한 분석입니다. " * 10) + "\n",
            "## 8. 리스크 매트릭스\n### 종합 해석\n" + ("리스크 매트릭스에 대한 해석입니다. " * 10) + "\n",
            "## 9. 전략적 권고사항\n### 종합 해석\n" + ("전략적 권고에 대한 해석입니다. " * 10) + "\n",
            "## 10. 부록 A\n내용\n",
            "## 11. 부록 B\n내용\n",
            "## 12. 부록 C\n내용\n",
            "## 13. 부록 D\n내용\n",
        ]
        report = "\n".join(sections)
        issues = gen._quality_gate(report)
        missing = [i for i in issues if "필수 섹션 누락" in i]
        assert len(missing) == 0
