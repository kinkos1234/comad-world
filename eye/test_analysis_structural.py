"""Tests for analysis/space_structural.py — StructuralSpace logic."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import networkx as nx

from analysis.base import SimulationData
from analysis.space_structural import StructuralSpace


def _make_sim_data(
    snapshots: list[dict] | None = None,
    graph: Any = None,
) -> SimulationData:
    snaps = snapshots or []
    return SimulationData(snapshots=snaps, graph=graph)


# ── _build_networkx_graph ──


class TestBuildNetworkxGraph:
    def test_no_graph(self):
        ss = StructuralSpace(_make_sim_data())
        G = ss._build_networkx_graph()
        assert G.number_of_nodes() == 0

    def test_entities_and_edges_loaded(self):
        graph = MagicMock()
        graph.query.side_effect = [
            [
                {"uid": "e1", "name": "E1", "cid": "c1", "stance": 0.5, "influence": 0.8},
                {"uid": "e2", "name": "E2", "cid": "c2", "stance": -0.3, "influence": 0.4},
            ],
            [
                {"src": "e1", "tgt": "e2", "rel": "INFLUENCES", "weight": 0.7},
            ],
        ]
        ss = StructuralSpace(_make_sim_data(graph=graph))
        G = ss._build_networkx_graph()
        assert G.number_of_nodes() == 2
        assert G.has_edge("e1", "e2")
        assert G.nodes["e1"]["name"] == "E1"

    def test_null_weight_raises_type_error(self):
        """weight=None is not handled by float() — documents actual behavior."""
        import pytest
        graph = MagicMock()
        graph.query.side_effect = [
            [{"uid": "a", "name": "A", "cid": "c1", "stance": 0, "influence": 0}],
            [{"src": "a", "tgt": "a", "rel": "R", "weight": None}],
        ]
        ss = StructuralSpace(_make_sim_data(graph=graph))
        with pytest.raises(TypeError):
            ss._build_networkx_graph()


# ── _analyze_centrality ──


class TestAnalyzeCentrality:
    def test_empty_graph(self):
        ss = StructuralSpace(_make_sim_data())
        result = ss._analyze_centrality(nx.DiGraph())
        assert result["nodes"] == {}
        assert result["top_risers"] == []
        assert result["top_fallers"] == []

    def test_basic_centrality(self):
        G = nx.DiGraph()
        G.add_node("a", name="A")
        G.add_node("b", name="B")
        G.add_node("c", name="C")
        G.add_edge("a", "b")
        G.add_edge("b", "c")
        G.add_edge("a", "c")

        ss = StructuralSpace(_make_sim_data())
        result = ss._analyze_centrality(G)
        assert "a" in result["nodes"]
        assert "betweenness" in result["nodes"]["a"]
        assert "pagerank" in result["nodes"]["a"]
        assert "degree" in result["nodes"]["a"]
        assert len(result["top_risers"]) <= 5
        assert len(result["top_fallers"]) <= 5

    def test_pagerank_failure_fallback(self):
        """If pagerank fails, should fallback to 0.0 for all nodes."""
        G = nx.DiGraph()
        G.add_node("a", name="A")
        # Single node with no edges -> pagerank may not converge
        ss = StructuralSpace(_make_sim_data())
        result = ss._analyze_centrality(G)
        assert result["nodes"]["a"]["pagerank"] >= 0.0


# ── _find_bridge_nodes ──


class TestFindBridgeNodes:
    def test_no_community_info(self):
        G = nx.DiGraph()
        G.add_node("a")
        G.add_node("b")
        G.add_edge("a", "b")
        ss = StructuralSpace(_make_sim_data())
        bridges = ss._find_bridge_nodes(G)
        assert bridges == []

    def test_single_community(self):
        G = nx.DiGraph()
        G.add_node("a", cid="c1")
        G.add_node("b", cid="c1")
        G.add_edge("a", "b")
        ss = StructuralSpace(_make_sim_data())
        bridges = ss._find_bridge_nodes(G)
        assert bridges == []

    def test_bridge_node_detected(self):
        G = nx.DiGraph()
        G.add_node("bridge", cid="c1", name="Bridge")
        G.add_node("a1", cid="c1")
        G.add_node("b1", cid="c2")
        G.add_node("c1_node", cid="c3")
        G.add_edge("bridge", "b1")
        G.add_edge("bridge", "c1_node")
        G.add_edge("a1", "bridge")

        ss = StructuralSpace(_make_sim_data())
        bridges = ss._find_bridge_nodes(G)
        assert len(bridges) >= 1
        bridge_nodes = {b["node"] for b in bridges}
        assert "bridge" in bridge_nodes

    def test_bridge_requires_2_external_communities(self):
        G = nx.DiGraph()
        G.add_node("a", cid="c1", name="A")
        G.add_node("b", cid="c2")
        G.add_edge("a", "b")
        ss = StructuralSpace(_make_sim_data())
        bridges = ss._find_bridge_nodes(G)
        # a connects to only 1 external community, so not a bridge
        assert len(bridges) == 0

    def test_sorted_by_bridge_count(self):
        G = nx.DiGraph()
        G.add_node("small_bridge", cid="c1", name="Small")
        G.add_node("big_bridge", cid="c1", name="Big")
        G.add_node("x", cid="c2")
        G.add_node("y", cid="c3")
        G.add_node("z", cid="c4")
        G.add_edge("small_bridge", "x")
        G.add_edge("small_bridge", "y")
        G.add_edge("big_bridge", "x")
        G.add_edge("big_bridge", "y")
        G.add_edge("big_bridge", "z")

        ss = StructuralSpace(_make_sim_data())
        bridges = ss._find_bridge_nodes(G)
        assert bridges[0]["node"] == "big_bridge"

    def test_capped_at_10(self):
        G = nx.DiGraph()
        for i in range(15):
            G.add_node(f"bridge_{i}", cid=f"c_{i}", name=f"B{i}")
            G.add_node(f"ext1_{i}", cid=f"cx_{i}")
            G.add_node(f"ext2_{i}", cid=f"cy_{i}")
            G.add_edge(f"bridge_{i}", f"ext1_{i}")
            G.add_edge(f"bridge_{i}", f"ext2_{i}")
        ss = StructuralSpace(_make_sim_data())
        bridges = ss._find_bridge_nodes(G)
        assert len(bridges) <= 10


# ── _find_structural_holes ──


class TestFindStructuralHoles:
    def test_single_community(self):
        G = nx.DiGraph()
        G.add_node("a", cid="c1")
        G.add_node("b", cid="c1")
        ss = StructuralSpace(_make_sim_data())
        holes = ss._find_structural_holes(G)
        assert holes == []

    def test_disconnected_communities(self):
        G = nx.DiGraph()
        G.add_node("a1", cid="c1")
        G.add_node("a2", cid="c1")
        G.add_node("b1", cid="c2")
        G.add_node("b2", cid="c2")
        # No edges between c1 and c2
        ss = StructuralSpace(_make_sim_data())
        holes = ss._find_structural_holes(G)
        assert len(holes) == 1
        assert holes[0]["density"] == 0.0
        assert holes[0]["edge_count"] == 0

    def test_well_connected_no_holes(self):
        G = nx.DiGraph()
        G.add_node("a", cid="c1")
        G.add_node("b", cid="c2")
        # Both directions
        G.add_edge("a", "b")
        G.add_edge("b", "a")
        ss = StructuralSpace(_make_sim_data())
        holes = ss._find_structural_holes(G)
        # density = 2 / (1*1*2) = 1.0, not < 0.05
        assert len(holes) == 0

    def test_sorted_by_density(self):
        G = nx.DiGraph()
        G.add_node("a1", cid="c1")
        G.add_node("b1", cid="c2")
        G.add_node("c1_node", cid="c3")
        G.add_edge("a1", "b1")  # c1-c2 has 1 edge
        # c1-c3 and c2-c3 have no edges
        ss = StructuralSpace(_make_sim_data())
        holes = ss._find_structural_holes(G)
        if len(holes) >= 2:
            assert holes[0]["density"] <= holes[1]["density"]

    def test_capped_at_10(self):
        G = nx.DiGraph()
        for i in range(15):
            G.add_node(f"n{i}", cid=f"c{i}")
        ss = StructuralSpace(_make_sim_data())
        holes = ss._find_structural_holes(G)
        assert len(holes) <= 10


# ── _analyze_edge_dynamics ──


class TestAnalyzeEdgeDynamics:
    def test_empty_snapshots(self):
        ss = StructuralSpace(_make_sim_data())
        result = ss._analyze_edge_dynamics()
        assert result["edge_creation_rate"] == {}
        assert result["edge_expiration_rate"] == {}
        assert result["net_growth_by_type"] == {}

    def test_action_create_edge(self):
        ss = StructuralSpace(_make_sim_data(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "actions": [
                            {
                                "actor": "a",
                                "effects": [
                                    {"type": "create_edge", "link_type": "ALLY"},
                                    {"type": "create_edge", "link_type": "ALLY"},
                                ],
                            },
                        ],
                    },
                },
            ]
        ))
        result = ss._analyze_edge_dynamics()
        assert result["edge_creation_rate"]["ALLY"] == 2

    def test_action_expire_edge(self):
        ss = StructuralSpace(_make_sim_data(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "actions": [
                            {
                                "actor": "a",
                                "effects": [
                                    {"type": "expire_edge", "relation": "OPPOSES"},
                                ],
                            },
                        ],
                    },
                },
            ]
        ))
        result = ss._analyze_edge_dynamics()
        assert result["edge_expiration_rate"]["OPPOSES"] == 1

    def test_meta_edge_create(self):
        ss = StructuralSpace(_make_sim_data(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "meta_edges": [
                            {"action": "create_edge", "link_type": "SYNERGY"},
                        ],
                    },
                },
            ]
        ))
        result = ss._analyze_edge_dynamics()
        assert result["edge_creation_rate"]["SYNERGY"] == 1

    def test_meta_edge_expire(self):
        ss = StructuralSpace(_make_sim_data(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "meta_edges": [
                            {"action": "expire_edge", "relation": "OPPOSES"},
                        ],
                    },
                },
            ]
        ))
        result = ss._analyze_edge_dynamics()
        assert result["edge_expiration_rate"]["OPPOSES"] == 1

    def test_net_growth(self):
        ss = StructuralSpace(_make_sim_data(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "actions": [
                            {
                                "actor": "a",
                                "effects": [
                                    {"type": "create_edge", "link_type": "ALLY"},
                                    {"type": "create_edge", "link_type": "ALLY"},
                                    {"type": "expire_edge", "relation": "ALLY"},
                                ],
                            },
                        ],
                    },
                },
            ]
        ))
        result = ss._analyze_edge_dynamics()
        assert result["net_growth_by_type"]["ALLY"] == 1  # 2 created - 1 expired

    def test_non_list_effects_skipped(self):
        ss = StructuralSpace(_make_sim_data(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "actions": [
                            {
                                "actor": "a",
                                "effects": "not_a_list",
                            },
                        ],
                    },
                },
            ]
        ))
        result = ss._analyze_edge_dynamics()
        assert result["edge_creation_rate"] == {}


class TestStructuralSpaceAnalyze:
    def test_full_analyze_no_graph(self):
        ss = StructuralSpace(_make_sim_data())
        result = ss.analyze()
        assert "centrality_changes" in result
        assert "bridge_nodes" in result
        assert "structural_holes" in result
        assert "edge_dynamics" in result

    def test_full_analyze_with_graph(self):
        graph = MagicMock()
        graph.query.side_effect = [
            [
                {"uid": "e1", "name": "E1", "cid": "c1", "stance": 0.5, "influence": 0.8},
                {"uid": "e2", "name": "E2", "cid": "c2", "stance": -0.3, "influence": 0.4},
                {"uid": "e3", "name": "E3", "cid": "c3", "stance": 0.1, "influence": 0.6},
            ],
            [
                {"src": "e1", "tgt": "e2", "rel": "INFLUENCES", "weight": 0.7},
                {"src": "e1", "tgt": "e3", "rel": "OPPOSES", "weight": 0.3},
                {"src": "e2", "tgt": "e3", "rel": "ALLY", "weight": 0.5},
            ],
        ]
        ss = StructuralSpace(_make_sim_data(graph=graph))
        result = ss.analyze()
        assert len(result["centrality_changes"]["nodes"]) == 3
