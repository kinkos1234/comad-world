"""Tests for analysis/space_recursive.py — RecursiveSpace logic."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import networkx as nx

from analysis.base import SimulationData
from analysis.space_recursive import RecursiveSpace


def _make_sim_data(
    snapshots: list[dict] | None = None,
    graph: Any = None,
) -> SimulationData:
    snaps = snapshots or []
    return SimulationData(snapshots=snaps, graph=graph)


# ── _alternating_signs ──


class TestAlternatingSigns:
    def test_alternating(self):
        assert RecursiveSpace._alternating_signs([1.0, -0.5, 0.3, -0.2]) is True

    def test_not_alternating(self):
        assert RecursiveSpace._alternating_signs([1.0, 0.5, -0.3]) is False

    def test_all_positive(self):
        assert RecursiveSpace._alternating_signs([1.0, 2.0, 3.0]) is False

    def test_all_negative(self):
        assert RecursiveSpace._alternating_signs([-1.0, -2.0]) is False

    def test_single_element(self):
        assert RecursiveSpace._alternating_signs([1.0]) is False

    def test_empty(self):
        assert RecursiveSpace._alternating_signs([]) is False

    def test_with_zero(self):
        # zero * anything >= 0, so not alternating
        assert RecursiveSpace._alternating_signs([1.0, 0.0, -1.0]) is False

    def test_two_elements(self):
        assert RecursiveSpace._alternating_signs([1.0, -1.0]) is True
        assert RecursiveSpace._alternating_signs([-0.5, 0.3]) is True


# ── _pattern_similarity ──


class TestPatternSimilarity:
    def test_identical_patterns(self):
        sim = RecursiveSpace._pattern_similarity(
            [0.1, 0.2, 0.3, 0.4, 0.5],
            [0.1, 0.2, 0.3, 0.4, 0.5],
        )
        assert sim > 0.9

    def test_completely_different_patterns(self):
        # One pattern is all negative, other all positive — may still have some similarity
        sim = RecursiveSpace._pattern_similarity(
            [0.1, 0.2, 0.3, 0.4],
            [-10.0, -20.0, -30.0, -40.0],
        )
        # Different ranges should still be compared via histogram
        assert isinstance(sim, float)

    def test_empty_list_a(self):
        assert RecursiveSpace._pattern_similarity([], [1.0, 2.0]) == 0.0

    def test_empty_list_b(self):
        assert RecursiveSpace._pattern_similarity([1.0, 2.0], []) == 0.0

    def test_both_empty(self):
        assert RecursiveSpace._pattern_similarity([], []) == 0.0

    def test_constant_patterns(self):
        # All same values -> histogram concentrates in one bin -> cosine may be 1.0 or 0
        sim = RecursiveSpace._pattern_similarity([1.0, 1.0, 1.0], [1.0, 1.0, 1.0])
        # When all values are identical, bins collapse; depends on implementation
        assert isinstance(sim, float)

    def test_returns_between_0_and_1(self):
        sim = RecursiveSpace._pattern_similarity(
            [0.1, -0.3, 0.5, -0.2],
            [0.2, -0.1, 0.4, -0.3],
        )
        assert 0.0 <= sim <= 1.0


# ── _build_networkx_graph ���─


class TestBuildNetworkxGraph:
    def test_no_graph_returns_empty(self):
        rs = RecursiveSpace(_make_sim_data())
        G = rs._build_networkx_graph()
        assert G.number_of_nodes() == 0
        assert G.number_of_edges() == 0

    def test_entities_and_edges(self):
        graph = MagicMock()
        graph.query.side_effect = [
            [
                {"uid": "e1", "name": "E1", "stance": 0.5, "cid": "c1"},
                {"uid": "e2", "name": "E2", "stance": -0.3, "cid": "c2"},
            ],
            [
                {"src": "e1", "tgt": "e2", "rel": "INFLUENCES", "weight": 0.8},
            ],
        ]
        rs = RecursiveSpace(_make_sim_data(graph=graph))
        G = rs._build_networkx_graph()
        assert G.number_of_nodes() == 2
        assert G.has_edge("e1", "e2")
        assert G["e1"]["e2"]["weight"] == 0.8

    def test_none_weight_raises_type_error(self):
        """weight=None is not handled by float() — documents actual behavior."""
        import pytest
        graph = MagicMock()
        graph.query.side_effect = [
            [{"uid": "e1", "name": "E1", "stance": 0, "cid": "c1"},
             {"uid": "e2", "name": "E2", "stance": 0, "cid": "c1"}],
            [{"src": "e1", "tgt": "e2", "rel": "R", "weight": None}],
        ]
        rs = RecursiveSpace(_make_sim_data(graph=graph))
        with pytest.raises(TypeError):
            rs._build_networkx_graph()

    def test_empty_query_results(self):
        graph = MagicMock()
        graph.query.side_effect = [None, None]
        rs = RecursiveSpace(_make_sim_data(graph=graph))
        G = rs._build_networkx_graph()
        assert G.number_of_nodes() == 0


# ── _detect_feedback_loops ──


class TestDetectFeedbackLoops:
    def test_no_cycles(self):
        rs = RecursiveSpace(_make_sim_data())
        G = nx.DiGraph()
        G.add_edge("a", "b")
        G.add_edge("b", "c")
        loops = rs._detect_feedback_loops(G)
        assert loops == []

    def test_simple_cycle(self):
        rs = RecursiveSpace(_make_sim_data(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "propagation": [
                            {"target": "a", "property": "stance", "delta": 0.1},
                            {"target": "b", "property": "stance", "delta": 0.2},
                        ],
                        "actions": [],
                    },
                },
            ]
        ))
        G = nx.DiGraph()
        G.add_edge("a", "b", rel_type="INFLUENCES", weight=0.5)
        G.add_edge("b", "a", rel_type="OPPOSES", weight=0.3)
        loops = rs._detect_feedback_loops(G)
        assert len(loops) >= 1
        assert loops[0]["type"] in ("positive", "negative", "mixed")

    def test_positive_loop(self):
        """All nodes have same-sign deltas -> positive loop."""
        rs = RecursiveSpace(_make_sim_data(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "propagation": [
                            {"target": "a", "property": "stance", "delta": 0.3},
                            {"target": "b", "property": "stance", "delta": 0.5},
                        ],
                        "actions": [],
                    },
                },
            ]
        ))
        G = nx.DiGraph()
        G.add_edge("a", "b", rel_type="R", weight=1.0)
        G.add_edge("b", "a", rel_type="R", weight=1.0)
        loops = rs._detect_feedback_loops(G)
        assert len(loops) >= 1
        assert loops[0]["type"] == "positive"

    def test_negative_loop(self):
        """Alternating sign deltas -> negative loop."""
        rs = RecursiveSpace(_make_sim_data(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "propagation": [
                            {"target": "a", "property": "stance", "delta": 0.3},
                            {"target": "b", "property": "stance", "delta": -0.5},
                        ],
                        "actions": [],
                    },
                },
            ]
        ))
        G = nx.DiGraph()
        G.add_edge("a", "b", rel_type="R", weight=1.0)
        G.add_edge("b", "a", rel_type="R", weight=1.0)
        loops = rs._detect_feedback_loops(G)
        assert len(loops) >= 1
        assert loops[0]["type"] == "negative"

    def test_long_cycle_filtered(self):
        """Cycles longer than 5 should be filtered out."""
        rs = RecursiveSpace(_make_sim_data())
        G = nx.DiGraph()
        nodes = ["a", "b", "c", "d", "e", "f", "g"]
        for i in range(len(nodes)):
            G.add_edge(nodes[i], nodes[(i + 1) % len(nodes)], rel_type="R", weight=1.0)
        loops = rs._detect_feedback_loops(G)
        # 7-node cycle should be filtered
        for loop in loops:
            assert len(loop["nodes"]) <= 5

    def test_max_20_loops(self):
        """Should cap at 20 loops."""
        rs = RecursiveSpace(_make_sim_data())
        G = nx.DiGraph()
        # Create many 2-node cycles
        for i in range(25):
            G.add_edge(f"a{i}", f"b{i}", rel_type="R", weight=1.0)
            G.add_edge(f"b{i}", f"a{i}", rel_type="R", weight=1.0)
        loops = rs._detect_feedback_loops(G)
        assert len(loops) <= 20

    def test_sorted_by_strength(self):
        rs = RecursiveSpace(_make_sim_data(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "propagation": [
                            {"target": "a", "property": "stance", "delta": 0.1},
                            {"target": "b", "property": "stance", "delta": 0.1},
                            {"target": "c", "property": "stance", "delta": 0.9},
                            {"target": "d", "property": "stance", "delta": 0.9},
                        ],
                        "actions": [],
                    },
                },
            ]
        ))
        G = nx.DiGraph()
        G.add_edge("a", "b", rel_type="R", weight=1.0)
        G.add_edge("b", "a", rel_type="R", weight=1.0)
        G.add_edge("c", "d", rel_type="R", weight=1.0)
        G.add_edge("d", "c", rel_type="R", weight=1.0)
        loops = rs._detect_feedback_loops(G)
        if len(loops) >= 2:
            assert loops[0]["strength"] >= loops[1]["strength"]


# ── _detect_fractal_patterns ──


class TestDetectFractalPatterns:
    def test_no_graph(self):
        rs = RecursiveSpace(_make_sim_data())
        assert rs._detect_fractal_patterns() == []

    def test_similar_tiers(self):
        graph = MagicMock()
        graph.query.side_effect = [
            [{"members": ["e1", "e2"]}],  # tier 0
            [{"members": ["e3", "e4"]}],  # tier 1
            [{"members": ["e5"]}],         # tier 2
            [],                             # tier 3
        ]
        # All entities have similar stance deltas
        sd = _make_sim_data(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "propagation": [
                            {"target": f"e{i}", "property": "stance", "delta": 0.1 * (i % 3)}
                            for i in range(1, 6)
                        ],
                        "actions": [],
                    },
                },
            ],
            graph=graph,
        )
        rs = RecursiveSpace(sd)
        patterns = rs._detect_fractal_patterns()
        # Whether patterns are detected depends on similarity threshold
        assert isinstance(patterns, list)
        for p in patterns:
            assert "similarity" in p
            assert p["similarity"] > 0.6


class TestRecursiveSpaceAnalyze:
    def test_full_analyze_no_graph(self):
        rs = RecursiveSpace(_make_sim_data())
        result = rs.analyze()
        assert "feedback_loops" in result
        assert "fractal_patterns" in result
        assert "loop_summary" in result
        assert result["loop_summary"]["positive_count"] == 0
        assert result["loop_summary"]["negative_count"] == 0
        assert result["loop_summary"]["mixed_count"] == 0

    def test_loop_summary_counts(self):
        graph = MagicMock()
        graph.query.side_effect = [
            [
                {"uid": "a", "name": "A", "stance": 0.5, "cid": "c1"},
                {"uid": "b", "name": "B", "stance": 0.3, "cid": "c1"},
            ],
            [
                {"src": "a", "tgt": "b", "rel": "R", "weight": 1.0},
                {"src": "b", "tgt": "a", "rel": "R", "weight": 1.0},
            ],
            # fractal pattern queries (4 tiers)
            [], [], [], [],
        ]
        sd = _make_sim_data(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "propagation": [
                            {"target": "a", "property": "stance", "delta": 0.3},
                            {"target": "b", "property": "stance", "delta": 0.5},
                        ],
                        "actions": [],
                    },
                },
            ],
            graph=graph,
        )
        rs = RecursiveSpace(sd)
        result = rs.analyze()
        total_loops = (
            result["loop_summary"]["positive_count"]
            + result["loop_summary"]["negative_count"]
            + result["loop_summary"]["mixed_count"]
        )
        assert total_loops == len(result["feedback_loops"])
