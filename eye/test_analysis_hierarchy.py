"""Tests for analysis/space_hierarchy.py — HierarchySpace logic."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from analysis.base import SimulationData
from analysis.space_hierarchy import HierarchySpace


def _make_sim_data(
    snapshots: list[dict] | None = None,
    graph: Any = None,
) -> SimulationData:
    """Build SimulationData with optional graph mock."""
    snaps = snapshots or []
    events: list[dict] = []
    actions: list[dict] = []
    for snap in snaps:
        r = snap.get("round", 0)
        for e in snap.get("changes", {}).get("events", []):
            e.setdefault("round", r)
            events.append(e)
        for a in snap.get("changes", {}).get("actions", []):
            a.setdefault("round", r)
            actions.append(a)
    return SimulationData(
        snapshots=snaps,
        events_log=events,
        actions_log=actions,
        graph=graph,
    )


class TestFindDominantEvent:
    def test_empty_snapshots(self):
        sd = _make_sim_data()
        hs = HierarchySpace(sd)
        assert hs._find_dominant_event(["e1", "e2"]) == ""

    def test_finds_strongest_source(self):
        sd = _make_sim_data(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "propagation": [
                            {"target": "e1", "source": "ev_major", "delta": 0.8},
                            {"target": "e1", "source": "ev_minor", "delta": 0.1},
                            {"target": "e2", "source": "ev_major", "delta": 0.3},
                        ],
                    },
                },
            ]
        )
        hs = HierarchySpace(sd)
        dominant = hs._find_dominant_event(["e1", "e2"])
        assert dominant == "ev_major"

    def test_ignores_non_members(self):
        sd = _make_sim_data(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "propagation": [
                            {"target": "outsider", "source": "ev_big", "delta": 5.0},
                            {"target": "e1", "source": "ev_small", "delta": 0.1},
                        ],
                    },
                },
            ]
        )
        hs = HierarchySpace(sd)
        assert hs._find_dominant_event(["e1"]) == "ev_small"


class TestDetectPropagationDirection:
    def test_mixed_when_single_tier(self):
        tier_analysis = {
            "C0": {"comm1": {"stance_delta": 0.5, "volatility_delta": 0.1}},
        }
        sd = _make_sim_data()
        hs = HierarchySpace(sd)
        assert hs._detect_propagation_direction(tier_analysis) == "mixed"

    def test_top_down_when_lower_tier_bigger(self):
        # Tier 0 (lower numbered = "top") has larger delta
        tier_analysis = {
            "C0": {"c1": {"stance_delta": 1.0, "volatility_delta": 0.5}},
            "C2": {"c2": {"stance_delta": 0.1, "volatility_delta": 0.05}},
        }
        sd = _make_sim_data()
        hs = HierarchySpace(sd)
        direction = hs._detect_propagation_direction(tier_analysis)
        assert direction == "top_down"

    def test_bottom_up_when_higher_tier_bigger(self):
        tier_analysis = {
            "C0": {"c1": {"stance_delta": 0.01, "volatility_delta": 0.01}},
            "C3": {"c2": {"stance_delta": 1.0, "volatility_delta": 0.5}},
        }
        sd = _make_sim_data()
        hs = HierarchySpace(sd)
        direction = hs._detect_propagation_direction(tier_analysis)
        assert direction == "bottom_up"

    def test_mixed_when_no_data(self):
        sd = _make_sim_data()
        hs = HierarchySpace(sd)
        assert hs._detect_propagation_direction({}) == "mixed"

    def test_skips_non_dict_values(self):
        tier_analysis = {
            "C0": "not_a_dict",
            "C1": {"c1": {"stance_delta": 0.5, "volatility_delta": 0.1}},
        }
        sd = _make_sim_data()
        hs = HierarchySpace(sd)
        # Single valid tier -> mixed
        assert hs._detect_propagation_direction(tier_analysis) == "mixed"

    def test_very_small_delta_ignored(self):
        tier_analysis = {
            "C0": {"c1": {"stance_delta": 0.0005, "volatility_delta": 0.0}},
            "C1": {"c2": {"stance_delta": 0.5, "volatility_delta": 0.1}},
        }
        sd = _make_sim_data()
        hs = HierarchySpace(sd)
        # C0 total delta < 0.001, so filtered out; single valid tier -> mixed
        assert hs._detect_propagation_direction(tier_analysis) == "mixed"


class TestAnalyzeTiersNoGraph:
    def test_returns_empty_without_graph(self):
        sd = _make_sim_data()
        hs = HierarchySpace(sd)
        result = hs._analyze_tiers()
        assert result == {}


class TestAnalyzeTiersWithGraph:
    def _make_graph_mock(self, tier_communities: dict[int, list[dict]]) -> MagicMock:
        """Create a mock graph that returns communities per tier."""
        graph = MagicMock()

        def query_side_effect(query_str, **kwargs):
            if "community_tier = $tier" in query_str:
                tier = kwargs.get("tier", 0)
                return tier_communities.get(tier, [])
            elif "community_id IS NOT NULL" in query_str and "community_tier" not in query_str:
                return tier_communities.get(0, [])
            return []

        graph.query.side_effect = query_side_effect
        return graph

    def test_basic_tier_analysis(self):
        graph = self._make_graph_mock({
            0: [{"cid": "c0_1", "members": ["e1", "e2"]}],
        })
        sd = _make_sim_data(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "propagation": [
                            {"target": "e1", "source": "ev1", "property": "stance", "delta": 0.5},
                        ],
                        "actions": [
                            {"actor": "e2", "action": "flip"},
                        ],
                    },
                },
            ],
            graph=graph,
        )
        hs = HierarchySpace(sd)
        result = hs._analyze_tiers()
        assert "C0" in result
        assert "c0_1" in result["C0"]
        assert result["C0"]["c0_1"]["member_count"] == 2
        assert result["C0"]["c0_1"]["action_count"] >= 1

    def test_fallback_tier0_query(self):
        """When tier=0 returns nothing from the tier-specific query,
        it should fall back to community_id query without tier."""
        graph = MagicMock()
        call_count = {"count": 0}

        def query_side_effect(query_str, **kwargs):
            call_count["count"] += 1
            if "community_tier = $tier" in query_str:
                tier = kwargs.get("tier", 0)
                if tier == 0:
                    return []  # No tier-specific results
                return []
            elif "community_id IS NOT NULL" in query_str:
                return [{"cid": "fallback_c", "members": ["e1"]}]
            return []

        graph.query.side_effect = query_side_effect
        sd = _make_sim_data(graph=graph)
        hs = HierarchySpace(sd)
        result = hs._analyze_tiers()
        assert "C0" in result
        assert "fallback_c" in result["C0"]


class TestHierarchySpaceAnalyze:
    def test_analyze_no_graph(self):
        sd = _make_sim_data()
        hs = HierarchySpace(sd)
        result = hs.analyze()
        assert "tier_analysis" in result
        assert "propagation_direction" in result
        assert "most_dynamic_tier" in result
        assert "most_dynamic_community" in result

    def test_most_dynamic_tier_selection(self):
        """Ensure the tier with largest combined delta is selected."""
        graph = MagicMock()

        def query_side_effect(query_str, **kwargs):
            tier = kwargs.get("tier", 0)
            if "community_tier = $tier" in query_str:
                if tier == 0:
                    return [{"cid": "c0", "members": ["e1"]}]
                elif tier == 1:
                    return [{"cid": "c1", "members": ["e2"]}]
                return []
            return []

        graph.query.side_effect = query_side_effect
        sd = _make_sim_data(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "propagation": [
                            {"target": "e1", "source": "ev1", "property": "stance", "delta": 0.1},
                            {"target": "e2", "source": "ev2", "property": "stance", "delta": 0.9},
                        ],
                        "actions": [],
                    },
                },
            ],
            graph=graph,
        )
        hs = HierarchySpace(sd)
        result = hs.analyze()
        # C1 has larger delta via e2
        assert result["most_dynamic_tier"] == "C1"
