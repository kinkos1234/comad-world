"""Tests for narrative builder — rule-based report section generation."""

from __future__ import annotations

from narration.narrative_builder import NarrativeBuilder


def _make_builder(**overrides) -> NarrativeBuilder:
    """Create a NarrativeBuilder with minimal default data."""
    defaults = {
        "aggregated": {
            "simulation_summary": {
                "total_rounds": 5,
                "total_events": 3,
                "total_actions": 2,
                "total_meta_edges_fired": 1,
                "community_migrations": 0,
            },
            "key_findings": [
                {"finding": "Root cause A", "confidence": 0.9, "supporting_spaces": ["causal"]},
            ],
        },
        "causal": {
            "causal_dag": {
                "nodes": 10,
                "edges": 15,
                "root_causes": [{"node": "entity_a", "downstream": 5}],
                "terminal_effects": ["entity_z"],
            },
            "causal_chains": [],
        },
        "structural": {
            "bridge_nodes": [
                {"node": "bridge_1", "name": "Bridge 1", "bridges": ["c1", "c2"]},
            ],
            "structural_holes": [{"hole": "h1"}],
            "centrality_changes": {
                "nodes": {},
                "top_risers": [],
            },
        },
        "hierarchy": {
            "most_dynamic_tier": "C0",
            "propagation_direction": "top_down",
            "tier_dynamics": {},
        },
        "temporal": {
            "leading_indicators": [],
            "lifecycle_phases": {},
            "event_reactions": {},
        },
        "recursive": {
            "feedback_loops": [],
            "loop_summary": {"positive_count": 0, "negative_count": 0},
        },
        "cross_space": {
            "cross_insights": [],
            "meta_patterns": [],
        },
    }
    defaults.update(overrides)
    return NarrativeBuilder(**defaults)


class TestBuildScenarios:
    def test_produces_three_scenarios(self):
        builder = _make_builder()
        parts = builder.build_scenarios()
        text = "\n".join(parts)
        assert "시나리오 1" in text
        assert "시나리오 2" in text
        assert "시나리오 3" in text

    def test_high_activity_mentions_primary_cause(self):
        builder = _make_builder(
            aggregated={
                "simulation_summary": {
                    "total_rounds": 5,
                    "total_events": 3,
                    "total_actions": 10,
                    "total_meta_edges_fired": 5,
                    "community_migrations": 0,
                },
                "key_findings": [],
            }
        )
        parts = builder.build_scenarios()
        text = "\n".join(parts)
        assert "entity a" in text.lower() or "entity_a" in text.lower()


class TestBuildRiskMatrix:
    def test_empty_risks(self):
        builder = _make_builder(
            structural={"bridge_nodes": [], "structural_holes": []},
            causal={"causal_dag": {"root_causes": []}},
        )
        parts = builder.build_risk_matrix()
        text = "\n".join(parts)
        assert "감지되지 않았습니다" in text

    def test_bridge_risk(self):
        builder = _make_builder()
        parts = builder.build_risk_matrix()
        text = "\n".join(parts)
        assert "Bridge 1" in text or "bridge" in text.lower()


class TestBuildRecommendations:
    def test_root_cause_recommendation(self):
        builder = _make_builder()
        parts = builder.build_recommendations()
        text = "\n".join(parts)
        assert "entity a" in text.lower() or "entity_a" in text.lower()
        assert "근본 원인" in text

    def test_bridge_recommendation(self):
        builder = _make_builder()
        parts = builder.build_recommendations()
        text = "\n".join(parts)
        assert "Bridge 1" in text or "브릿지" in text

    def test_empty_recommendations(self):
        builder = _make_builder(
            causal={"causal_dag": {"root_causes": []}},
            structural={"bridge_nodes": [], "structural_holes": []},
        )
        parts = builder.build_recommendations()
        text = "\n".join(parts)
        assert "데이터가 충분하지 않습니다" in text


class TestBuildEntityProfiles:
    def test_with_top_risers(self):
        builder = _make_builder(
            structural={
                "bridge_nodes": [],
                "structural_holes": [],
                "centrality_changes": {
                    "nodes": {},
                    "top_risers": [
                        {
                            "node": "e1", "name": "Entity One",
                            "stance": 0.5, "volatility": 0.3,
                            "influence_score": 0.8,
                            "degree": 0.1, "pagerank": 0.05,
                            "betweenness": 0.02,
                        }
                    ],
                },
            }
        )
        parts = builder.build_entity_profiles()
        text = "\n".join(parts)
        assert "Entity One" in text

    def test_no_data(self):
        builder = _make_builder(
            structural={
                "bridge_nodes": [],
                "structural_holes": [],
                "centrality_changes": {"nodes": {}, "top_risers": []},
            }
        )
        parts = builder.build_entity_profiles()
        text = "\n".join(parts)
        assert "데이터가 없습니다" in text


class TestBuildNetworkEvolution:
    def test_basic_output(self):
        builder = _make_builder()
        parts = builder.build_network_evolution()
        text = "\n".join(parts)
        assert "시뮬레이션 역학 요약" in text
        assert "5라운드" in text
