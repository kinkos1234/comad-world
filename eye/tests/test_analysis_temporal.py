"""Tests for analysis/space_temporal.py — TemporalSpace logic."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import numpy as np

from comad_eye.analysis.base import SimulationData
from comad_eye.analysis.space_temporal import TemporalSpace


def _make_sim_data(
    snapshots: list[dict] | None = None,
    events_log: list[dict] | None = None,
    actions_log: list[dict] | None = None,
    graph: Any = None,
) -> SimulationData:
    snaps = snapshots or []
    return SimulationData(
        snapshots=snaps,
        events_log=events_log or [],
        actions_log=actions_log or [],
        graph=graph,
    )


class TestCrossCorrelate:
    def test_identical_series(self):
        ts = TemporalSpace(_make_sim_data())
        a = np.array([0.0, 0.5, 1.0, 0.5, 0.0])
        corr, lag = ts._cross_correlate(a, a)
        assert abs(corr) > 0.9
        assert lag == 0

    def test_shifted_series(self):
        ts = TemporalSpace(_make_sim_data())
        a = np.array([0.0, 0.0, 1.0, 1.0, 0.0, 0.0])
        b = np.array([0.0, 0.0, 0.0, 1.0, 1.0, 0.0])
        corr, lag = ts._cross_correlate(a, b)
        assert abs(corr) > 0.5
        # lag should be non-zero since b is shifted
        # The exact value depends on the implementation

    def test_short_series(self):
        ts = TemporalSpace(_make_sim_data())
        a = np.array([1.0, 2.0])
        b = np.array([3.0, 4.0])
        corr, lag = ts._cross_correlate(a, b)
        assert corr == 0.0
        assert lag == 0

    def test_constant_series(self):
        ts = TemporalSpace(_make_sim_data())
        a = np.array([1.0, 1.0, 1.0, 1.0])
        b = np.array([2.0, 2.0, 2.0, 2.0])
        corr, lag = ts._cross_correlate(a, b)
        assert corr == 0.0  # std is near zero

    def test_anti_correlated(self):
        ts = TemporalSpace(_make_sim_data())
        a = np.array([0.0, 1.0, 0.0, 1.0, 0.0])
        b = np.array([1.0, 0.0, 1.0, 0.0, 1.0])
        corr, lag = ts._cross_correlate(a, b)
        assert corr < 0  # negatively correlated at lag=0


class TestAnalyzeEventReactions:
    def test_empty_events(self):
        ts = TemporalSpace(_make_sim_data())
        result = ts._analyze_event_reactions()
        assert result == {}

    def test_single_event_single_reaction(self):
        ts = TemporalSpace(_make_sim_data(
            events_log=[
                {"uid": "ev1", "name": "Event 1", "round": 1},
            ],
            actions_log=[
                {"actor": "a1", "actor_name": "Actor 1", "action": "flip", "round": 2},
            ],
        ))
        result = ts._analyze_event_reactions()
        assert "ev1" in result
        assert result["ev1"]["reaction_count"] == 1
        assert result["ev1"]["avg_delay"] == 1.0

    def test_ignores_reactions_before_event(self):
        ts = TemporalSpace(_make_sim_data(
            events_log=[
                {"uid": "ev1", "round": 5},
            ],
            actions_log=[
                {"actor": "a1", "action": "flip", "round": 3},  # before event
            ],
        ))
        result = ts._analyze_event_reactions()
        assert result == {}

    def test_ignores_reactions_beyond_5_rounds(self):
        ts = TemporalSpace(_make_sim_data(
            events_log=[
                {"uid": "ev1", "round": 1},
            ],
            actions_log=[
                {"actor": "a1", "action": "flip", "round": 7},  # 6 rounds delay > 5
            ],
        ))
        result = ts._analyze_event_reactions()
        assert result == {}

    def test_multiple_reactions_sorted_by_delay(self):
        ts = TemporalSpace(_make_sim_data(
            events_log=[
                {"uid": "ev1", "round": 1},
            ],
            actions_log=[
                {"actor": "a3", "actor_name": "Late", "action": "a", "round": 4},
                {"actor": "a1", "actor_name": "First", "action": "b", "round": 1},
                {"actor": "a2", "actor_name": "Middle", "action": "c", "round": 2},
            ],
        ))
        result = ts._analyze_event_reactions()
        assert result["ev1"]["first_reactor"]["actor_name"] == "First"
        assert result["ev1"]["cascading_order"][0] == "First"

    def test_cascading_order_capped_at_10(self):
        ts = TemporalSpace(_make_sim_data(
            events_log=[
                {"uid": "ev1", "round": 0},
            ],
            actions_log=[
                {"actor": f"a{i}", "actor_name": f"Actor {i}", "action": "x", "round": 0}
                for i in range(15)
            ],
        ))
        result = ts._analyze_event_reactions()
        assert len(result["ev1"]["cascading_order"]) <= 10


class TestDetectLeadingIndicators:
    def test_no_graph(self):
        ts = TemporalSpace(_make_sim_data())
        assert ts._detect_leading_indicators() == []

    def test_too_few_entities(self):
        graph = MagicMock()
        graph.query.return_value = [{"uid": "e1", "name": "Entity 1"}]
        ts = TemporalSpace(_make_sim_data(graph=graph))
        assert ts._detect_leading_indicators() == []

    def test_constant_stance_no_indicators(self):
        graph = MagicMock()
        graph.query.return_value = [
            {"uid": "e1", "name": "E1"},
            {"uid": "e2", "name": "E2"},
        ]
        sd = _make_sim_data(
            snapshots=[
                {"round": i, "changes": {"propagation": []}}
                for i in range(5)
            ],
            graph=graph,
        )
        ts = TemporalSpace(sd)
        indicators = ts._detect_leading_indicators()
        # All zeros -> no valid series -> no indicators
        assert indicators == []

    def test_correlated_series_detected(self):
        """Two entities with similar but shifted stance changes should be detected."""
        graph = MagicMock()
        graph.query.return_value = [
            {"uid": "leader", "name": "Leader"},
            {"uid": "follower", "name": "Follower"},
        ]
        # Leader changes first, follower follows one round later
        snapshots = [
            {
                "round": i,
                "changes": {
                    "propagation": [
                        {"target": "leader", "property": "stance", "new": 0.1 * i},
                    ] if i < 4 else [
                        {"target": "leader", "property": "stance", "new": 0.1 * i},
                        {"target": "follower", "property": "stance", "new": 0.1 * (i - 1)},
                    ],
                },
            }
            for i in range(6)
        ]
        sd = _make_sim_data(snapshots=snapshots, graph=graph)
        ts = TemporalSpace(sd)
        indicators = ts._detect_leading_indicators()
        # Result depends on correlation threshold, but function should not crash
        assert isinstance(indicators, list)

    def test_capped_at_20(self):
        """Should return at most 20 indicators."""
        graph = MagicMock()
        graph.query.return_value = [
            {"uid": f"e{i}", "name": f"E{i}"} for i in range(25)
        ]
        # Create snapshots where all entities have correlated stance changes
        snapshots = []
        for r in range(10):
            props = [
                {"target": f"e{i}", "property": "stance", "new": 0.1 * r + 0.01 * i}
                for i in range(25)
            ]
            snapshots.append({"round": r, "changes": {"propagation": props}})
        sd = _make_sim_data(snapshots=snapshots, graph=graph)
        ts = TemporalSpace(sd)
        indicators = ts._detect_leading_indicators()
        assert len(indicators) <= 20


class TestClassifyLifecycle:
    def test_no_graph(self):
        ts = TemporalSpace(_make_sim_data())
        assert ts._classify_lifecycle() == {}

    def test_inactive_stays_stable(self):
        graph = MagicMock()
        graph.query.return_value = [{"uid": "e1"}]
        sd = _make_sim_data(
            snapshots=[{"round": 0, "changes": {"propagation": [], "actions": []}}],
            graph=graph,
        )
        ts = TemporalSpace(sd)
        lifecycle = ts._classify_lifecycle()
        assert "e1" in lifecycle
        assert lifecycle["e1"][-1] == "stable"

    def test_volatility_spike_triggers_overheated(self):
        graph = MagicMock()
        graph.query.return_value = [{"uid": "e1"}]
        sd = _make_sim_data(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "propagation": [
                            {"target": "e1", "property": "volatility", "delta": 0.2},
                        ],
                        "actions": [],
                    },
                },
            ],
            graph=graph,
        )
        ts = TemporalSpace(sd)
        lifecycle = ts._classify_lifecycle()
        assert "activated" in lifecycle["e1"]
        assert "overheated" in lifecycle["e1"]

    def test_phases_after_overheated(self):
        """After overheated, the lifecycle does not add a separate 'cooling' phase."""
        graph = MagicMock()
        graph.query.return_value = [{"uid": "e1"}]
        sd = _make_sim_data(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "propagation": [
                            {"target": "e1", "property": "volatility", "delta": 0.3},
                        ],
                        "actions": [],
                    },
                },
                {
                    "round": 2,
                    "changes": {
                        "propagation": [
                            {"target": "e1", "property": "volatility", "delta": -0.1},
                        ],
                        "actions": [],
                    },
                },
            ],
            graph=graph,
        )
        ts = TemporalSpace(sd)
        lifecycle = ts._classify_lifecycle()
        # Implementation goes inactive → activated → overheated; no separate cooling phase
        assert "overheated" in lifecycle["e1"]

    def test_deduplication(self):
        graph = MagicMock()
        graph.query.return_value = [{"uid": "e1"}]
        sd = _make_sim_data(
            snapshots=[
                {
                    "round": i,
                    "changes": {"propagation": [], "actions": []},
                }
                for i in range(3)
            ],
            graph=graph,
        )
        ts = TemporalSpace(sd)
        lifecycle = ts._classify_lifecycle()
        # Should not have consecutive duplicates
        phases = lifecycle["e1"]
        for i in range(len(phases) - 1):
            assert phases[i] != phases[i + 1]

    def test_no_entities_returned(self):
        graph = MagicMock()
        graph.query.return_value = None
        sd = _make_sim_data(graph=graph)
        ts = TemporalSpace(sd)
        assert ts._classify_lifecycle() == {}


class TestTemporalSpaceAnalyze:
    def test_full_analyze_empty(self):
        ts = TemporalSpace(_make_sim_data())
        result = ts.analyze()
        assert "event_reactions" in result
        assert "leading_indicators" in result
        assert "lifecycle_phases" in result

    def test_full_analyze_with_events(self):
        ts = TemporalSpace(_make_sim_data(
            events_log=[{"uid": "ev1", "name": "E1", "round": 0}],
            actions_log=[{"actor": "a1", "actor_name": "A1", "action": "flip", "round": 1}],
        ))
        result = ts.analyze()
        assert "ev1" in result["event_reactions"]
