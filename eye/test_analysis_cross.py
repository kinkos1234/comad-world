"""Tests for analysis/space_cross.py — CrossSpace cross-space analysis."""

from __future__ import annotations

from typing import Any

from analysis.base import SimulationData
from analysis.space_cross import CrossSpace


def _empty_sim() -> SimulationData:
    return SimulationData()


def _make_cross(
    hierarchy: dict[str, Any] | None = None,
    temporal: dict[str, Any] | None = None,
    recursive: dict[str, Any] | None = None,
    structural: dict[str, Any] | None = None,
    causal: dict[str, Any] | None = None,
) -> CrossSpace:
    return CrossSpace(
        data=_empty_sim(),
        hierarchy=hierarchy or {},
        temporal=temporal or {},
        recursive=recursive or {},
        structural=structural or {},
        causal=causal or {},
    )


class TestCorrelateHierarchyTemporal:
    def test_top_down(self):
        cs = _make_cross(hierarchy={"propagation_direction": "top_down"})
        insights = cs._correlate_hierarchy_temporal()
        assert len(insights) >= 1
        assert insights[0]["confidence"] == 0.8
        assert "거시" in insights[0]["finding"]

    def test_bottom_up(self):
        cs = _make_cross(hierarchy={"propagation_direction": "bottom_up"})
        insights = cs._correlate_hierarchy_temporal()
        assert len(insights) >= 1
        assert "미시" in insights[0]["finding"]

    def test_mixed_no_insight(self):
        cs = _make_cross(hierarchy={"propagation_direction": "mixed"})
        insights = cs._correlate_hierarchy_temporal()
        assert len(insights) == 0

    def test_dynamic_tier_with_leaders(self):
        cs = _make_cross(
            hierarchy={"most_dynamic_tier": "C2"},
            temporal={"leading_indicators": [{"leader": "a", "follower": "b"}]},
        )
        insights = cs._correlate_hierarchy_temporal()
        assert len(insights) >= 1
        found = any("C2" in i["finding"] for i in insights)
        assert found


class TestCorrelateStructuralCausal:
    def test_bridge_as_causal_intermediate(self):
        cs = _make_cross(
            structural={
                "bridge_nodes": [
                    {"node": "nodeX", "name": "Node X", "bridges": ["c1", "c2"]},
                ],
            },
            causal={
                "causal_chains": [
                    {"path": ["root", "nodeX", "leaf"]},
                ],
            },
        )
        insights = cs._correlate_structural_causal()
        assert len(insights) == 1
        assert insights[0]["node"] == "nodeX"
        assert insights[0]["confidence"] == 0.85

    def test_no_overlap(self):
        cs = _make_cross(
            structural={
                "bridge_nodes": [
                    {"node": "bridgeA", "name": "A", "bridges": ["c1", "c2"]},
                ],
            },
            causal={
                "causal_chains": [
                    {"path": ["root", "other", "leaf"]},
                ],
            },
        )
        insights = cs._correlate_structural_causal()
        assert len(insights) == 0

    def test_short_chain_no_intermediate(self):
        cs = _make_cross(
            structural={
                "bridge_nodes": [
                    {"node": "bridgeA", "name": "A", "bridges": ["c1", "c2"]},
                ],
            },
            causal={
                "causal_chains": [
                    {"path": ["root", "leaf"]},  # len=2, no intermediate
                ],
            },
        )
        insights = cs._correlate_structural_causal()
        assert len(insights) == 0


class TestCorrelateRecursiveTemporal:
    def test_positive_loop_leaders_overlap(self):
        cs = _make_cross(
            recursive={
                "feedback_loops": [
                    {"type": "positive", "nodes": ["e1", "e2"]},
                ],
            },
            temporal={
                "leading_indicators": [{"leader": "e1", "follower": "e3"}],
            },
        )
        insights = cs._correlate_recursive_temporal()
        assert any("선행지표" in i["finding"] for i in insights)

    def test_both_positive_and_negative_loops(self):
        cs = _make_cross(
            recursive={
                "feedback_loops": [
                    {"type": "positive", "nodes": ["e1"]},
                    {"type": "negative", "nodes": ["e2"]},
                ],
            },
        )
        insights = cs._correlate_recursive_temporal()
        assert any("공존" in i["finding"] for i in insights)

    def test_no_loops(self):
        cs = _make_cross(recursive={"feedback_loops": []})
        insights = cs._correlate_recursive_temporal()
        assert len(insights) == 0


class TestCorrelateHierarchyCausal:
    def test_with_root_causes_and_dynamic_tier(self):
        cs = _make_cross(
            hierarchy={"most_dynamic_tier": "C1"},
            causal={
                "causal_dag": {
                    "root_causes": [{"node": "a"}, {"node": "b"}],
                },
            },
        )
        insights = cs._correlate_hierarchy_causal()
        assert len(insights) == 1
        assert "C1" in insights[0]["finding"]

    def test_no_root_causes(self):
        cs = _make_cross(
            hierarchy={"most_dynamic_tier": "C0"},
            causal={"causal_dag": {"root_causes": []}},
        )
        insights = cs._correlate_hierarchy_causal()
        assert len(insights) == 0


class TestCorrelateStructuralRecursive:
    def test_holes_no_loops(self):
        cs = _make_cross(
            structural={"structural_holes": [{"pair": ["c1", "c2"]}]},
            recursive={"feedback_loops": []},
        )
        insights = cs._correlate_structural_recursive()
        assert len(insights) == 1
        assert "차단" in insights[0]["finding"]

    def test_no_holes_with_loops(self):
        cs = _make_cross(
            structural={"structural_holes": []},
            recursive={"feedback_loops": [{"type": "positive", "nodes": ["a"]}]},
        )
        insights = cs._correlate_structural_recursive()
        assert len(insights) == 1
        assert "활발" in insights[0]["finding"]

    def test_both_present(self):
        cs = _make_cross(
            structural={"structural_holes": [{"pair": ["c1", "c2"]}]},
            recursive={"feedback_loops": [{"type": "positive", "nodes": ["a"]}]},
        )
        insights = cs._correlate_structural_recursive()
        assert len(insights) == 0


class TestExtractMetaPatterns:
    def test_bridge_leverage_point(self):
        """Bridge + causal intermediate + feedback loop node = triple."""
        insights = [
            {
                "spaces": ["structural", "causal"],
                "node": "hub",
                "finding": "hub is bridge and causal intermediate",
            },
        ]
        cs = _make_cross(
            recursive={"feedback_loops": [{"nodes": ["hub", "other"]}]},
        )
        patterns = cs._extract_meta_patterns(insights)
        assert any(p["name"] == "bridge_leverage_point" for p in patterns)

    def test_hierarchy_temporal_inversion(self):
        cs = _make_cross(hierarchy={"propagation_direction": "bottom_up"})
        patterns = cs._extract_meta_patterns([])
        assert any(p["name"] == "hierarchy_temporal_inversion" for p in patterns)

    def test_causal_recursive_resonance(self):
        cs = _make_cross(
            causal={
                "causal_dag": {
                    "root_causes": [],
                    "terminal_effects": ["loop_start"],
                },
            },
            recursive={
                "feedback_loops": [
                    {"type": "positive", "nodes": ["loop_start", "other"]},
                ],
            },
        )
        patterns = cs._extract_meta_patterns([])
        assert any(p["name"] == "causal_recursive_resonance" for p in patterns)


class TestCrossSpaceAnalyze:
    def test_full_analyze_empty_inputs(self):
        cs = _make_cross()
        result = cs.analyze()
        assert "cross_insights" in result
        assert "meta_patterns" in result
        assert "insight_count" in result
        assert "meta_pattern_count" in result
        assert result["insight_count"] == len(result["cross_insights"])

    def test_full_analyze_with_data(self):
        cs = _make_cross(
            hierarchy={"propagation_direction": "top_down", "most_dynamic_tier": "C0"},
            temporal={"leading_indicators": [{"leader": "x"}]},
            structural={
                "bridge_nodes": [
                    {"node": "bridge", "name": "Bridge", "bridges": ["c1", "c2"]},
                ],
                "structural_holes": [],
            },
            recursive={
                "feedback_loops": [
                    {"type": "positive", "nodes": ["a"]},
                    {"type": "negative", "nodes": ["b"]},
                ],
            },
            causal={
                "causal_dag": {"root_causes": [{"node": "r1"}]},
                "causal_chains": [{"path": ["r1", "bridge", "leaf"]}],
            },
        )
        result = cs.analyze()
        assert result["insight_count"] > 0
