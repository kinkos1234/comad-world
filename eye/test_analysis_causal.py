"""Tests for analysis/space_causal.py — CausalSpace logic."""

from __future__ import annotations

from typing import Any

import networkx as nx
import pytest

from analysis.base import SimulationData
from analysis.space_causal import CausalSpace


def _make_sim_data(snapshots: list[dict[str, Any]] | None = None) -> SimulationData:
    """Build SimulationData from raw snapshot dicts."""
    snaps = snapshots or []
    events: list[dict] = []
    actions: list[dict] = []
    meta_edges: list[dict] = []
    for snap in snaps:
        r = snap.get("round", 0)
        for e in snap.get("changes", {}).get("events", []):
            e.setdefault("round", r)
            events.append(e)
        for a in snap.get("changes", {}).get("actions", []):
            a.setdefault("round", r)
            actions.append(a)
        for m in snap.get("changes", {}).get("meta_edges", []):
            m.setdefault("round", r)
            meta_edges.append(m)
    return SimulationData(
        snapshots=snaps,
        events_log=events,
        actions_log=actions,
        meta_edges_log=meta_edges,
    )


class TestBuildCausalDag:
    def test_empty_data(self):
        cs = CausalSpace(_make_sim_data())
        dag = cs._build_causal_dag()
        assert dag.number_of_nodes() == 0
        assert dag.number_of_edges() == 0

    def test_propagation_creates_edges(self):
        sd = _make_sim_data([
            {
                "round": 1,
                "changes": {
                    "propagation": [
                        {"source": "A", "target": "B", "delta": 0.5},
                        {"source": "A", "target": "C", "delta": 0.3},
                    ],
                },
            },
        ])
        cs = CausalSpace(sd)
        dag = cs._build_causal_dag()
        assert dag.has_edge("A", "B")
        assert dag.has_edge("A", "C")
        assert dag["A"]["B"]["weight"] == pytest.approx(0.5)

    def test_self_edges_ignored(self):
        sd = _make_sim_data([
            {
                "round": 1,
                "changes": {
                    "propagation": [
                        {"source": "A", "target": "A", "delta": 0.5},
                    ],
                },
            },
        ])
        cs = CausalSpace(sd)
        dag = cs._build_causal_dag()
        assert not dag.has_edge("A", "A")

    def test_empty_source_or_target_ignored(self):
        sd = _make_sim_data([
            {
                "round": 1,
                "changes": {
                    "propagation": [
                        {"source": "", "target": "B", "delta": 0.5},
                        {"source": "A", "target": "", "delta": 0.3},
                    ],
                },
            },
        ])
        cs = CausalSpace(sd)
        dag = cs._build_causal_dag()
        assert dag.number_of_edges() == 0

    def test_weight_accumulates(self):
        sd = _make_sim_data([
            {
                "round": 1,
                "changes": {
                    "propagation": [
                        {"source": "A", "target": "B", "delta": 0.3},
                    ],
                },
            },
            {
                "round": 2,
                "changes": {
                    "propagation": [
                        {"source": "A", "target": "B", "delta": 0.2},
                    ],
                },
            },
        ])
        cs = CausalSpace(sd)
        dag = cs._build_causal_dag()
        assert dag["A"]["B"]["weight"] == pytest.approx(0.5)

    def test_meta_edge_creates_edge(self):
        sd = _make_sim_data([
            {
                "round": 1,
                "changes": {
                    "meta_edges": [
                        {"source": "X", "target": "Y", "effect": 0.7},
                    ],
                },
            },
        ])
        cs = CausalSpace(sd)
        dag = cs._build_causal_dag()
        assert dag.has_edge("X", "Y")
        assert dag["X"]["Y"]["type"] == "meta_edge"

    def test_action_creates_edges(self):
        sd = _make_sim_data([
            {
                "round": 1,
                "changes": {
                    "actions": [
                        {
                            "actor": "A",
                            "action": "ally",
                            "effects": [
                                {"target": "B", "delta": 0.4},
                                {"target": "C", "delta": 0.2},
                            ],
                        },
                    ],
                },
            },
        ])
        cs = CausalSpace(sd)
        dag = cs._build_causal_dag()
        assert dag.has_edge("A", "B")
        assert dag.has_edge("A", "C")
        assert dag["A"]["B"]["type"] == "action"

    def test_action_non_dict_effects_ignored(self):
        sd = _make_sim_data([
            {
                "round": 1,
                "changes": {
                    "actions": [
                        {
                            "actor": "A",
                            "action": "flip",
                            "effects": ["not_a_dict"],
                        },
                    ],
                },
            },
        ])
        cs = CausalSpace(sd)
        dag = cs._build_causal_dag()
        assert dag.number_of_edges() == 0

    def test_event_node_created(self):
        sd = _make_sim_data([
            {
                "round": 1,
                "changes": {
                    "events": [{"uid": "ev1"}],
                },
            },
        ])
        cs = CausalSpace(sd)
        dag = cs._build_causal_dag()
        assert "ev1" in dag.nodes
        assert dag.nodes["ev1"]["type"] == "event"


class TestRemoveCycles:
    def test_removes_cycle(self):
        cs = CausalSpace(_make_sim_data())
        dag = nx.DiGraph()
        dag.add_edge("A", "B", weight=1.0)
        dag.add_edge("B", "C", weight=0.5)
        dag.add_edge("C", "A", weight=0.1)
        cs._remove_cycles(dag)
        assert nx.is_directed_acyclic_graph(dag)

    def test_removes_weakest_edge(self):
        cs = CausalSpace(_make_sim_data())
        dag = nx.DiGraph()
        dag.add_edge("A", "B", weight=1.0)
        dag.add_edge("B", "A", weight=0.1)
        cs._remove_cycles(dag)
        assert nx.is_directed_acyclic_graph(dag)
        # The weakest edge (B->A, weight=0.1) should be removed
        assert dag.has_edge("A", "B")
        assert not dag.has_edge("B", "A")

    def test_already_dag(self):
        cs = CausalSpace(_make_sim_data())
        dag = nx.DiGraph()
        dag.add_edge("A", "B", weight=1.0)
        dag.add_edge("B", "C", weight=0.5)
        cs._remove_cycles(dag)
        assert dag.number_of_edges() == 2


class TestFindRootCausesAndTerminals:
    def test_root_causes(self):
        cs = CausalSpace(_make_sim_data())
        dag = nx.DiGraph()
        dag.add_edge("root1", "mid")
        dag.add_edge("root2", "mid")
        dag.add_edge("mid", "leaf")
        roots = cs._find_root_causes(dag)
        assert set(roots) == {"root1", "root2"}

    def test_terminal_effects(self):
        cs = CausalSpace(_make_sim_data())
        dag = nx.DiGraph()
        dag.add_edge("root", "mid")
        dag.add_edge("mid", "leaf1")
        dag.add_edge("mid", "leaf2")
        terminals = cs._find_terminal_effects(dag)
        assert set(terminals) == {"leaf1", "leaf2"}

    def test_root_causes_sorted_by_descendants(self):
        cs = CausalSpace(_make_sim_data())
        dag = nx.DiGraph()
        dag.add_edge("big_root", "m1")
        dag.add_edge("big_root", "m2")
        dag.add_edge("m1", "leaf1")
        dag.add_edge("m2", "leaf2")
        dag.add_edge("small_root", "leaf3")
        roots = cs._find_root_causes(dag)
        assert roots[0] == "big_root"

    def test_empty_dag(self):
        cs = CausalSpace(_make_sim_data())
        dag = nx.DiGraph()
        assert cs._find_root_causes(dag) == []
        assert cs._find_terminal_effects(dag) == []


class TestTotalImpact:
    def test_linear_chain(self):
        cs = CausalSpace(_make_sim_data())
        dag = nx.DiGraph()
        dag.add_edge("A", "B", weight=0.5)
        dag.add_edge("B", "C", weight=0.4)
        impact = cs._total_impact(dag, "A")
        # A->B: 0.5, A->B->C: 0.5*0.4 = 0.2, total = 0.7
        assert impact == pytest.approx(0.7, abs=0.01)

    def test_no_descendants(self):
        cs = CausalSpace(_make_sim_data())
        dag = nx.DiGraph()
        dag.add_node("A")
        assert cs._total_impact(dag, "A") == 0.0


class TestImpactAnalysis:
    def test_basic_impact(self):
        cs = CausalSpace(_make_sim_data())
        dag = nx.DiGraph()
        dag.add_edge("root", "child1", weight=0.8)
        dag.add_edge("root", "child2", weight=0.3)
        result = cs._impact_analysis(dag, ["root"])
        assert "root" in result
        assert result["root"]["downstream_count"] == 2

    def test_empty_root_causes(self):
        cs = CausalSpace(_make_sim_data())
        dag = nx.DiGraph()
        result = cs._impact_analysis(dag, [])
        assert result == {}


class TestExtractCausalChains:
    def test_basic_chain_extraction(self):
        sd = _make_sim_data([
            {
                "round": 1,
                "changes": {
                    "propagation": [
                        {"source": "A", "target": "B", "delta": 0.5},
                        {"source": "B", "target": "C", "delta": 0.3},
                    ],
                },
            },
        ])
        cs = CausalSpace(sd)
        dag = cs._build_causal_dag()
        roots = cs._find_root_causes(dag)
        chains = cs._extract_causal_chains(dag, roots)
        assert len(chains) >= 1
        # Should have chain from A to C
        found_a_c = any(
            c["root"] == "A" and c["terminal"] == "C" for c in chains
        )
        assert found_a_c

    def test_sorted_by_weight(self):
        sd = _make_sim_data([
            {
                "round": 1,
                "changes": {
                    "propagation": [
                        {"source": "A", "target": "B", "delta": 0.9},
                        {"source": "B", "target": "C", "delta": 0.8},
                        {"source": "D", "target": "E", "delta": 0.1},
                        {"source": "E", "target": "F", "delta": 0.1},
                    ],
                },
            },
        ])
        cs = CausalSpace(sd)
        dag = cs._build_causal_dag()
        roots = cs._find_root_causes(dag)
        chains = cs._extract_causal_chains(dag, roots)
        if len(chains) >= 2:
            assert chains[0]["total_weight"] >= chains[1]["total_weight"]


class TestCausalSpaceAnalyze:
    def test_full_analyze_empty(self):
        cs = CausalSpace(_make_sim_data())
        result = cs.analyze()
        assert "causal_dag" in result
        assert "impact_analysis" in result
        assert "root_cause_ranking" in result
        assert "causal_chains" in result
        assert result["causal_dag"]["nodes"] == 0

    def test_full_analyze_with_data(self):
        sd = _make_sim_data([
            {
                "round": 1,
                "changes": {
                    "propagation": [
                        {"source": "A", "target": "B", "delta": 0.5},
                        {"source": "B", "target": "C", "delta": 0.3},
                    ],
                    "events": [{"uid": "A"}],
                },
            },
        ])
        cs = CausalSpace(sd)
        result = cs.analyze()
        assert result["causal_dag"]["nodes"] >= 3
        assert result["causal_dag"]["edges"] >= 2
