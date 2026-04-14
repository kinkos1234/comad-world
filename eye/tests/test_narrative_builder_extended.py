"""Extended tests for narration/narrative_builder.py — coverage supplement.

Covers additional paths in: _narrate(), build_recommendations(),
build_risk_matrix(), build_scenarios(), build_entity_profiles(),
build_network_evolution(), build_lens_synthesis(),
build_ontology_appendix(), build_simulation_timeline().
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from comad_eye.narration.narrative_builder import NarrativeBuilder


# ───────────────────── Fixtures ─────────────────────


def _mock_llm(return_value: str = "LLM 서사 보강 결과") -> MagicMock:
    llm = MagicMock()
    llm.generate.return_value = return_value
    return llm


def _make_builder(llm=None, **overrides) -> NarrativeBuilder:
    """Create a NarrativeBuilder with rich default data for coverage."""
    defaults = {
        "aggregated": {
            "simulation_summary": {
                "total_rounds": 10,
                "total_events": 5,
                "total_actions": 8,
                "total_meta_edges_fired": 4,
                "community_migrations": 2,
            },
            "key_findings": [
                {"finding": "Root cause Alpha", "confidence": 0.9, "supporting_spaces": ["causal"]},
                {"finding": "Bridge Beta connects", "confidence": 0.85, "supporting_spaces": ["structural"]},
            ],
        },
        "causal": {
            "causal_dag": {
                "nodes": 15,
                "edges": 20,
                "root_causes": [
                    {"node": "entity_alpha", "downstream": 5},
                    {"node": "entity_beta", "downstream": 3},
                ],
                "terminal_effects": ["entity_omega"],
            },
            "causal_chains": [],
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
                        "stance": 0.7,
                        "volatility": 0.6,
                        "influence_score": 0.9,
                        "degree": 0.15,
                        "pagerank": 0.12,
                        "betweenness": 0.2,
                    },
                },
                "top_risers": [
                    {
                        "node": "entity_alpha",
                        "uid": "entity_alpha",
                        "name": "Entity Alpha",
                        "stance": 0.7,
                        "volatility": 0.6,
                        "influence_score": 0.9,
                        "degree": 0.15,
                        "pagerank": 0.12,
                        "betweenness": 0.2,
                    },
                ],
            },
        },
        "hierarchy": {
            "most_dynamic_tier": "C0",
            "propagation_direction": "top_down",
            "tier_dynamics": {
                "T0": {"avg_volatility": 0.05, "node_count": 3},
                "T1": {"avg_volatility": 0.35, "node_count": 7},
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
            },
            "event_reactions": {},
        },
        "recursive": {
            "feedback_loops": [
                {"type": "positive", "nodes": ["entity_alpha", "entity_gamma", "entity_alpha"]},
            ],
            "loop_summary": {"positive_count": 1, "negative_count": 1},
        },
        "cross_space": {
            "cross_insights": [],
            "meta_patterns": [],
        },
    }
    defaults.update(overrides)
    return NarrativeBuilder(**defaults, llm=llm)


# ───────────────────── _narrate (LLM augmentation) ─────────────────────


class TestNarrate:
    def test_with_llm(self):
        llm = _mock_llm("서사 보강 텍스트")
        builder = _make_builder(llm=llm)
        result = builder._narrate("skeleton", "question")
        assert result == "서사 보강 텍스트"
        assert llm.generate.called

    def test_without_llm(self):
        builder = _make_builder(llm=None)
        result = builder._narrate("skeleton", "question")
        assert result == ""

    def test_llm_failure_returns_empty(self):
        llm = MagicMock()
        llm.generate.side_effect = Exception("LLM error")
        builder = _make_builder(llm=llm)
        result = builder._narrate("skeleton", "question")
        assert result == ""

    def test_llm_returns_none(self):
        llm = _mock_llm(None)
        builder = _make_builder(llm=llm)
        result = builder._narrate("skeleton", "question")
        assert result == ""

    def test_llm_returns_empty_string(self):
        llm = _mock_llm("")
        builder = _make_builder(llm=llm)
        result = builder._narrate("skeleton", "question")
        assert result == ""


# ───────────────────── Recommendations ─────────────────────


class TestBuildRecommendationsExtended:
    def test_root_cause_with_high_downstream(self):
        builder = _make_builder()
        parts = builder.build_recommendations()
        text = "\n".join(parts)
        assert "근본 원인" in text
        assert "entity alpha" in text

    def test_bridge_node_recommendation(self):
        builder = _make_builder()
        parts = builder.build_recommendations()
        text = "\n".join(parts)
        assert "Bridge One" in text or "브릿지" in text.lower()

    def test_feedback_loop_recommendation(self):
        builder = _make_builder()
        parts = builder.build_recommendations()
        text = "\n".join(parts)
        assert "피드백 루프" in text

    def test_structural_holes_recommendation(self):
        builder = _make_builder()
        parts = builder.build_recommendations()
        text = "\n".join(parts)
        assert "구조적 공백" in text

    def test_lens_cross_recommendation(self):
        builder = _make_builder(
            lens_cross=[
                {
                    "lens_name": "Taleb",
                    "actionable_insight": "Take action on fragility",
                },
            ],
        )
        parts = builder.build_recommendations()
        text = "\n".join(parts)
        assert "Take action on fragility" in text

    def test_low_downstream_skips_root_cause(self):
        builder = _make_builder(
            causal={
                "causal_dag": {
                    "root_causes": [{"node": "small", "downstream": 1}],
                },
            },
        )
        parts = builder.build_recommendations()
        text = "\n".join(parts)
        # downstream < 2, so root cause recommendation should not appear
        assert "근본 원인 관리" not in text

    def test_empty_recommendations(self):
        builder = _make_builder(
            causal={"causal_dag": {"root_causes": []}},
            structural={"bridge_nodes": [], "structural_holes": [], "centrality_changes": {"nodes": {}, "top_risers": []}},
            recursive={"feedback_loops": [], "loop_summary": {"positive_count": 0, "negative_count": 0}},
        )
        parts = builder.build_recommendations()
        text = "\n".join(parts)
        assert "데이터가 충분하지 않습니다" in text

    def test_with_llm_narration(self):
        llm = _mock_llm("우선 실행해야 할 것은 Alpha 관리입니다.")
        builder = _make_builder(llm=llm)
        parts = builder.build_recommendations()
        text = "\n".join(parts)
        assert "우선 실행 판단" in text


# ───────────────────── Risk Matrix ─────────────────────


class TestBuildRiskMatrixExtended:
    def test_bridge_risk(self):
        builder = _make_builder()
        parts = builder.build_risk_matrix()
        text = "\n".join(parts)
        assert "Bridge One" in text

    def test_root_cause_risk(self):
        builder = _make_builder()
        parts = builder.build_risk_matrix()
        text = "\n".join(parts)
        assert "의존도 과집중" in text

    def test_feedback_loop_risk(self):
        builder = _make_builder(
            recursive={
                "feedback_loops": [
                    {"type": "positive", "nodes": ["a", "b"]},
                    {"type": "positive", "nodes": ["c", "d"]},
                ],
                "loop_summary": {"positive_count": 2, "negative_count": 0},
            },
        )
        parts = builder.build_risk_matrix()
        text = "\n".join(parts)
        assert "과열 가능성" in text

    def test_lens_risk(self):
        builder = _make_builder(
            lens_insights={
                "causal": [
                    {
                        "lens_id": "taleb",
                        "lens_name": "Taleb",
                        "risk_assessment": "Black swan risk detected",
                    },
                ],
            },
        )
        parts = builder.build_risk_matrix()
        text = "\n".join(parts)
        assert "Black swan" in text

    def test_kahneman_lens_risk(self):
        builder = _make_builder(
            lens_insights={
                "structural": [
                    {
                        "lens_id": "kahneman",
                        "lens_name": "Kahneman",
                        "risk": "Cognitive bias risk",
                    },
                ],
            },
        )
        parts = builder.build_risk_matrix()
        text = "\n".join(parts)
        assert "Cognitive bias" in text

    def test_no_risks(self):
        builder = _make_builder(
            structural={"bridge_nodes": [], "structural_holes": [], "centrality_changes": {"nodes": {}, "top_risers": []}},
            causal={"causal_dag": {"root_causes": []}},
            recursive={"feedback_loops": [], "loop_summary": {"positive_count": 0, "negative_count": 0}},
        )
        parts = builder.build_risk_matrix()
        text = "\n".join(parts)
        assert "감지되지 않았습니다" in text

    def test_bridge_high_impact(self):
        builder = _make_builder(
            structural={
                "bridge_nodes": [
                    {"node": "b1", "name": "Mega Bridge", "bridges": ["c1", "c2", "c3"]},
                ],
                "structural_holes": [],
                "centrality_changes": {"nodes": {}, "top_risers": []},
            },
        )
        parts = builder.build_risk_matrix()
        text = "\n".join(parts)
        assert "높음" in text  # n_bridges >= 3 -> high impact


# ───────────────────── Scenarios ─────────────────────


class TestBuildScenariosExtended:
    def test_low_activity_scenario(self):
        builder = _make_builder(
            aggregated={
                "simulation_summary": {
                    "total_rounds": 5,
                    "total_events": 1,
                    "total_actions": 0,
                    "total_meta_edges_fired": 1,
                    "community_migrations": 0,
                },
                "key_findings": [],
            },
        )
        parts = builder.build_scenarios()
        text = "\n".join(parts)
        assert "안정적 균형" in text

    def test_high_activity_scenario(self):
        builder = _make_builder()
        parts = builder.build_scenarios()
        text = "\n".join(parts)
        assert "entity alpha" in text
        assert "시나리오 1" in text

    def test_positive_scenario_with_bridges(self):
        builder = _make_builder()
        parts = builder.build_scenarios()
        text = "\n".join(parts)
        assert "시나리오 2" in text
        assert "Bridge One" in text

    def test_negative_scenario_with_positive_loops(self):
        builder = _make_builder()
        parts = builder.build_scenarios()
        text = "\n".join(parts)
        assert "시나리오 3" in text
        assert "양의 피드백" in text

    def test_negative_scenario_with_structural_holes(self):
        builder = _make_builder()
        parts = builder.build_scenarios()
        text = "\n".join(parts)
        assert "구조적 공백" in text

    def test_negative_scenario_no_holes(self):
        builder = _make_builder(
            structural={
                "bridge_nodes": [],
                "structural_holes": [],
                "centrality_changes": {"nodes": {}, "top_risers": []},
            },
        )
        parts = builder.build_scenarios()
        text = "\n".join(parts)
        assert "브릿지 노드의 이탈" in text

    def test_positive_scenario_with_neg_loops(self):
        builder = _make_builder()
        parts = builder.build_scenarios()
        text = "\n".join(parts)
        assert "음의 피드백 루프" in text

    def test_positive_scenario_no_neg_loops(self):
        builder = _make_builder(
            recursive={"feedback_loops": [], "loop_summary": {"positive_count": 0, "negative_count": 0}},
        )
        parts = builder.build_scenarios()
        text = "\n".join(parts)
        assert "자기 교정 메커니즘" in text

    def test_with_llm_narration(self):
        llm = _mock_llm("가장 가능성 높은 시나리오는 기본 경로입니다.")
        builder = _make_builder(llm=llm)
        parts = builder.build_scenarios()
        text = "\n".join(parts)
        assert "시나리오 종합 판단" in text

    def test_no_root_causes(self):
        builder = _make_builder(
            causal={"causal_dag": {"root_causes": []}, "causal_chains": []},
        )
        parts = builder.build_scenarios()
        text = "\n".join(parts)
        assert "주요 동인" in text  # fallback name


# ───────────────────── Entity Profiles ─────────────────────


class TestBuildEntityProfilesExtended:
    def test_with_top_risers(self):
        builder = _make_builder()
        parts = builder.build_entity_profiles()
        text = "\n".join(parts)
        assert "Entity Alpha" in text
        assert "Stance=" in text
        assert "Volatility=" in text

    def test_roles_root_cause(self):
        builder = _make_builder()
        parts = builder.build_entity_profiles()
        text = "\n".join(parts)
        assert "근본 원인" in text

    def test_roles_bridge_node(self):
        # Add entity_alpha as bridge node
        builder = _make_builder(
            structural={
                "bridge_nodes": [
                    {"node": "entity_alpha", "name": "Entity Alpha", "bridges": ["c1", "c2"]},
                ],
                "structural_holes": [],
                "centrality_changes": {
                    "nodes": {},
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
        )
        parts = builder.build_entity_profiles()
        text = "\n".join(parts)
        assert "브릿지 노드" in text

    def test_roles_high_influence(self):
        builder = _make_builder()
        parts = builder.build_entity_profiles()
        text = "\n".join(parts)
        assert "높은 영향력" in text  # pagerank > 0.1

    def test_roles_info_mediator(self):
        builder = _make_builder()
        parts = builder.build_entity_profiles()
        text = "\n".join(parts)
        assert "정보 중재자" in text  # betweenness > 0.1

    def test_roles_high_volatility(self):
        builder = _make_builder()
        parts = builder.build_entity_profiles()
        text = "\n".join(parts)
        assert "고변동성" in text  # volatility > 0.5

    def test_roles_strong_stance(self):
        builder = _make_builder()
        parts = builder.build_entity_profiles()
        text = "\n".join(parts)
        assert "강한 입장" in text  # stance > 0.6

    def test_risk_level_high(self):
        builder = _make_builder()
        parts = builder.build_entity_profiles()
        text = "\n".join(parts)
        assert "높음" in text  # volatility > 0.5

    def test_lifecycle_included(self):
        builder = _make_builder()
        parts = builder.build_entity_profiles()
        text = "\n".join(parts)
        assert "생명주기" in text

    def test_leading_indicator(self):
        builder = _make_builder()
        parts = builder.build_entity_profiles()
        text = "\n".join(parts)
        assert "선행지표" in text

    def test_no_data(self):
        builder = _make_builder(
            structural={
                "bridge_nodes": [],
                "structural_holes": [],
                "centrality_changes": {"nodes": {}, "top_risers": []},
            },
        )
        parts = builder.build_entity_profiles()
        text = "\n".join(parts)
        assert "데이터가 없습니다" in text or "충분한 데이터" in text

    def test_fallback_to_nodes_when_no_risers(self):
        builder = _make_builder(
            structural={
                "bridge_nodes": [],
                "structural_holes": [],
                "centrality_changes": {
                    "nodes": {
                        "ent_1": {
                            "node": "ent_1",
                            "name": "Node One",
                            "stance": 0.1,
                            "volatility": 0.1,
                            "influence_score": 0.5,
                            "degree": 0.05,
                            "pagerank": 0.03,
                            "betweenness": 0.02,
                        },
                    },
                    "top_risers": [],
                },
            },
        )
        parts = builder.build_entity_profiles()
        text = "\n".join(parts)
        assert "Node One" in text


# ───────────────────── Network Evolution ─────────────────────


class TestBuildNetworkEvolutionExtended:
    def test_basic_output(self):
        builder = _make_builder()
        parts = builder.build_network_evolution()
        text = "\n".join(parts)
        assert "시뮬레이션 역학 요약" in text
        assert "10라운드" in text

    def test_propagation_direction(self):
        builder = _make_builder()
        parts = builder.build_network_evolution()
        text = "\n".join(parts)
        assert "하향식 전파" in text

    def test_bottom_up_direction(self):
        builder = _make_builder(
            hierarchy={
                "propagation_direction": "bottom_up",
                "tier_dynamics": {},
                "most_dynamic_tier": "C0",
            },
        )
        parts = builder.build_network_evolution()
        text = "\n".join(parts)
        assert "상향식 전파" in text

    def test_mixed_direction(self):
        builder = _make_builder(
            hierarchy={
                "propagation_direction": "mixed",
                "tier_dynamics": {},
                "most_dynamic_tier": "C0",
            },
        )
        parts = builder.build_network_evolution()
        text = "\n".join(parts)
        assert "양방향 혼합" in text

    def test_tier_dynamics_table(self):
        builder = _make_builder()
        parts = builder.build_network_evolution()
        text = "\n".join(parts)
        assert "T0" in text
        assert "T1" in text
        assert "안정적" in text or "변동적" in text or "격변적" in text

    def test_leading_indicators_summary(self):
        builder = _make_builder()
        parts = builder.build_network_evolution()
        text = "\n".join(parts)
        assert "Entity Alpha" in text
        assert "Entity Omega" in text

    def test_key_findings(self):
        builder = _make_builder()
        parts = builder.build_network_evolution()
        text = "\n".join(parts)
        assert "Root cause Alpha" in text

    def test_empty_data(self):
        builder = _make_builder(
            aggregated={
                "simulation_summary": {
                    "total_rounds": 0,
                    "total_events": 0,
                    "total_actions": 0,
                    "total_meta_edges_fired": 0,
                    "community_migrations": 0,
                },
                "key_findings": [],
            },
            hierarchy={
                "propagation_direction": "mixed",
                "tier_dynamics": {},
                "most_dynamic_tier": "N/A",
            },
            temporal={"leading_indicators": [], "lifecycle_phases": {}},
        )
        parts = builder.build_network_evolution()
        text = "\n".join(parts)
        assert "0라운드" in text


# ───────────────────── Lens Synthesis ─────────────────────


class TestBuildLensSynthesisExtended:
    def test_empty_lens_cross(self):
        builder = _make_builder()
        parts = builder.build_lens_synthesis()
        assert parts == []

    def test_with_lens_cross_and_lens_data(self):
        builder = _make_builder(
            lens_insights={
                "causal": [
                    {
                        "risk_assessment": "High fragility risk",
                        "opportunity": "Antifragility chance",
                    },
                ],
            },
            lens_cross=[
                {
                    "lens_name": "Taleb",
                    "thinker": "Nassim Taleb",
                    "synthesis": "Cross synthesis",
                    "confidence": 0.85,
                },
            ],
        )
        parts = builder.build_lens_synthesis()
        text = "\n".join(parts)
        assert "렌즈 간 공통 리스크" in text
        assert "High fragility risk" in text
        assert "렌즈 간 공통 기회" in text
        assert "Antifragility chance" in text
        assert "렌즈 종합 판단" in text

    def test_risks_only(self):
        builder = _make_builder(
            lens_insights={
                "causal": [{"risk_assessment": "Risk only"}],
            },
            lens_cross=[
                {"lens_name": "X", "thinker": "Y", "synthesis": "S", "confidence": 0.5},
            ],
        )
        parts = builder.build_lens_synthesis()
        text = "\n".join(parts)
        assert "렌즈 간 공통 리스크" in text
        assert "렌즈 간 공통 기회" not in text

    def test_non_list_lens_insights_skipped(self):
        builder = _make_builder(
            lens_insights={"causal": "not_a_list"},
            lens_cross=[
                {"lens_name": "X", "thinker": "Y", "synthesis": "S", "confidence": 0.5},
            ],
        )
        parts = builder.build_lens_synthesis()
        text = "\n".join(parts)
        # Should not crash, just skip non-list values
        assert "렌즈 종합 판단" in text


# ───────────────────── Ontology Appendix ─────────────────────


class TestBuildOntologyAppendixExtended:
    def test_with_ontology_file(self, tmp_path):
        extraction_dir = tmp_path / "data" / "extraction"
        extraction_dir.mkdir(parents=True)
        data = {
            "entities": {
                "alpha": {
                    "uid": "alpha",
                    "name": "Alpha",
                    "object_type": "Actor",
                    "description": "Test entity",
                },
                "beta": {
                    "uid": "beta",
                    "name": "Beta",
                    "object_type": "Environment",
                    "description": "Another",
                },
            },
            "relationships": [
                {
                    "source_uid": "alpha",
                    "target_uid": "beta",
                    "link_type": "INFLUENCES",
                    "weight": 0.8,
                },
            ],
        }
        (extraction_dir / "comad_eye.ontology.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

        builder = _make_builder()
        with patch("comad_eye.narration.narrative_builder.Path"):
            # We need to mock the Path("data/extraction") in the method
            # Instead, let's directly call and rely on the actual path check
            pass

        # Since build_ontology_appendix uses hardcoded Path("data/extraction"),
        # we need to patch it
        with patch("comad_eye.narration.narrative_builder.Path") as MockPath:
            mock_extraction = MagicMock()
            mock_extraction.__truediv__ = MagicMock(side_effect=lambda x: extraction_dir / x)

            mock_ontology = MagicMock()
            mock_ontology.exists.return_value = True
            mock_ontology.read_text.return_value = json.dumps(data, ensure_ascii=False)

            def path_side_effect(arg):
                if arg == "data/extraction":
                    return mock_extraction
                return Path(arg)

            MockPath.side_effect = path_side_effect
            mock_extraction.__truediv__ = MagicMock(return_value=mock_ontology)

            parts = builder.build_ontology_appendix()
            text = "\n".join(parts)
            assert "Alpha" in text
            assert "INFLUENCES" in text

    def test_no_ontology_file(self):
        builder = _make_builder()
        with patch("comad_eye.narration.narrative_builder.Path") as MockPath:
            mock_extraction = MagicMock()
            mock_ontology = MagicMock()
            mock_ontology.exists.return_value = False
            mock_extraction.__truediv__ = MagicMock(return_value=mock_ontology)
            MockPath.return_value = mock_extraction

            parts = builder.build_ontology_appendix()
            text = "\n".join(parts)
            assert "온톨로지 데이터가 없습니다" in text

    def test_entities_as_list(self):
        builder = _make_builder()
        data = {
            "entities": [
                {"name": "Alpha", "object_type": "Actor", "description": "Test"},
            ],
            "relationships": [],
        }
        with patch("comad_eye.narration.narrative_builder.Path") as MockPath:
            mock_extraction = MagicMock()
            mock_ontology = MagicMock()
            mock_ontology.exists.return_value = True
            mock_ontology.read_text.return_value = json.dumps(data)
            mock_extraction.__truediv__ = MagicMock(return_value=mock_ontology)
            MockPath.return_value = mock_extraction

            parts = builder.build_ontology_appendix()
            text = "\n".join(parts)
            assert "Alpha" in text

    def test_string_entity_handling(self):
        builder = _make_builder()
        data = {
            "entities": ["entity_string_1", "entity_string_2"],
            "relationships": [],
        }
        with patch("comad_eye.narration.narrative_builder.Path") as MockPath:
            mock_extraction = MagicMock()
            mock_ontology = MagicMock()
            mock_ontology.exists.return_value = True
            mock_ontology.read_text.return_value = json.dumps(data)
            mock_extraction.__truediv__ = MagicMock(return_value=mock_ontology)
            MockPath.return_value = mock_extraction

            parts = builder.build_ontology_appendix()
            text = "\n".join(parts)
            assert "entity string 1" in text  # clean_name removes underscores

    def test_entity_type_distribution(self):
        builder = _make_builder()
        data = {
            "entities": [
                {"name": "A1", "object_type": "Actor", "description": "d"},
                {"name": "A2", "object_type": "Actor", "description": "d"},
                {"name": "E1", "object_type": "Event", "description": "d"},
            ],
            "relationships": [],
        }
        with patch("comad_eye.narration.narrative_builder.Path") as MockPath:
            mock_extraction = MagicMock()
            mock_ontology = MagicMock()
            mock_ontology.exists.return_value = True
            mock_ontology.read_text.return_value = json.dumps(data)
            mock_extraction.__truediv__ = MagicMock(return_value=mock_ontology)
            MockPath.return_value = mock_extraction

            parts = builder.build_ontology_appendix()
            text = "\n".join(parts)
            assert "엔티티 유형 분포" in text
            assert "Actor" in text
            assert "66.7%" in text  # 2/3


# ───────────────────── Simulation Timeline ─────────────────────


class TestBuildSimulationTimelineExtended:
    def test_no_snapshots_dir(self):
        builder = _make_builder()
        with patch("comad_eye.narration.narrative_builder.Path") as MockPath:
            mock_snapshots = MagicMock()
            mock_snapshots.exists.return_value = False
            MockPath.return_value = mock_snapshots

            parts = builder.build_simulation_timeline()
            text = "\n".join(parts)
            assert "스냅샷 데이터가 없습니다" in text

    def test_empty_snapshots_dir(self):
        builder = _make_builder()
        with patch("comad_eye.narration.narrative_builder.Path") as MockPath:
            mock_snapshots = MagicMock()
            mock_snapshots.exists.return_value = True
            mock_snapshots.glob.return_value = []
            MockPath.return_value = mock_snapshots

            parts = builder.build_simulation_timeline()
            text = "\n".join(parts)
            assert "스냅샷 데이터가 없습니다" in text

    def test_with_snapshot_files(self, tmp_path):
        snapshots_dir = tmp_path / "data" / "snapshots"
        snapshots_dir.mkdir(parents=True)

        for i in range(3):
            snap = {
                "round": i + 1,
                "changes": {
                    "events": [{"uid": f"event_{i}"}] if i == 0 else [],
                    "propagation": [
                        {"source": "A", "target": "B", "delta": 0.5},
                    ] if i == 1 else [],
                    "meta_edges": [],
                    "actions": [{"actor": "Alpha", "action": "act"}] if i == 2 else [],
                },
            }
            (snapshots_dir / f"round_{i + 1:03d}.json").write_text(
                json.dumps(snap), encoding="utf-8"
            )

        builder = _make_builder()
        with patch("comad_eye.narration.narrative_builder.Path") as MockPath:
            MockPath.return_value = snapshots_dir
            # We need the real Path behavior for glob
            MockPath.side_effect = None

        # Use the actual filesystem with patched Path
        with patch("comad_eye.narration.narrative_builder.Path", return_value=snapshots_dir):
            builder.build_simulation_timeline()
            # Since we're patching Path constructor, let's test with tmp_path directly
            # This test mainly verifies the code doesn't crash

    def test_snapshot_with_all_change_types(self, tmp_path):
        snapshots_dir = tmp_path / "snapshots"
        snapshots_dir.mkdir()

        snap = {
            "round": 1,
            "changes": {
                "events": [{"uid": "ev1"}],
                "propagation": [{"source": "A", "target": "B", "delta": 0.5}],
                "meta_edges": [{"edge": "me1"}],
                "actions": [{"actor": "Alpha", "action": "intervene"}],
            },
        }
        (snapshots_dir / "round_001.json").write_text(json.dumps(snap), encoding="utf-8")

        builder = _make_builder()
        # Manually test the parsing logic by calling with the correct Path
        # Since the method uses hardcoded "data/snapshots", we patch Path
        import comad_eye.narration.narrative_builder as nb_module

        original_path = nb_module.Path

        def mock_path(arg):
            if arg == "data/snapshots":
                return snapshots_dir
            return original_path(arg)

        with patch.object(nb_module, "Path", side_effect=mock_path):
            parts = builder.build_simulation_timeline()
            text = "\n".join(parts)
            assert "라운드" in text
            assert "총계" in text
