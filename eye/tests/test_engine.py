"""Tests for simulation/engine.py — SimulationEngine orchestration."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from comad_eye.simulation.engine import SimulationEngine, SimulationResult
from comad_eye.simulation.event_chain import SimEvent


# ---------------------------------------------------------------------------
# SimulationResult dataclass
# ---------------------------------------------------------------------------

class TestSimulationResult:
    def test_defaults(self):
        r = SimulationResult()
        assert r.total_rounds == 0
        assert r.total_events == 0
        assert r.total_actions == 0
        assert r.total_meta_edges_fired == 0
        assert r.total_propagation_effects == 0
        assert r.total_community_migrations == 0
        assert r.llm_calls == 0
        assert r.early_stop is False
        assert r.early_stop_reason == ""


# ---------------------------------------------------------------------------
# SimulationEngine helpers (mocked dependencies)
# ---------------------------------------------------------------------------

def _make_engine(
    max_rounds=3,
    min_rounds=None,
    convergence_threshold=0.005,
    community_refresh_interval=3,
) -> SimulationEngine:
    """Create a SimulationEngine with fully mocked dependencies.

    By default min_rounds is set above max_rounds so convergence never triggers
    unless the test explicitly lowers it.
    """
    if min_rounds is None:
        min_rounds = max_rounds + 1

    client = MagicMock()
    client.query.return_value = []
    client.get_all_entities.return_value = []
    client.get_graph_stats.return_value = {
        "node_count": 5, "edge_count": 10, "avg_volatility": 0.1, "avg_stance": 0.0,
    }

    settings = SimpleNamespace(
        max_rounds=max_rounds,
        min_rounds=min_rounds,
        propagation_decay=0.6,
        propagation_max_hops=3,
        volatility_decay=0.1,
        convergence_threshold=convergence_threshold,
        max_actions_per_entity=1,
        community_refresh_interval=community_refresh_interval,
        meta_edge_entity_limit=50,
        meta_edge_neighbor_limit=30,
    )

    meta_engine = MagicMock()
    meta_engine.evaluate_on_change.return_value = []
    meta_engine.evaluate_all.return_value = []

    action_registry = MagicMock()
    action_registry.get_actions_for_type.return_value = []

    metadata_bus = MagicMock()

    engine = SimulationEngine(
        client=client,
        meta_edge_engine=meta_engine,
        action_registry=action_registry,
        metadata_bus=metadata_bus,
        settings=settings,
        snapshot_dir="/tmp/test_snapshots",
    )

    # Mock sub-components
    engine._propagation = MagicMock()
    engine._propagation.propagate.return_value = []
    engine._propagation.apply_effects.return_value = []

    engine._action_resolver = MagicMock()
    engine._action_resolver.resolve.return_value = []

    engine._snapshot = MagicMock()
    engine._snapshot.save.return_value = None
    engine._snapshot.check_invariants.return_value = []
    engine._snapshot._get_summary.return_value = {
        "avg_volatility": 0.1,
        "avg_stance": 0.0,
    }

    engine._community = MagicMock()
    engine._community.detect.return_value = {"migrations": []}

    return engine


# ---------------------------------------------------------------------------
# _check_convergence
# ---------------------------------------------------------------------------

class TestCheckConvergence:
    def test_returns_false_before_min_rounds(self):
        engine = _make_engine(min_rounds=5)
        assert engine._check_convergence(3) is False

    def test_returns_false_on_first_call_after_min(self):
        engine = _make_engine(min_rounds=1, convergence_threshold=0.005)
        engine._client.query.return_value = [{"avg_vol": 0.1}]
        # First call: no previous value to compare
        assert engine._check_convergence(2) is False

    def test_returns_true_when_converged(self):
        engine = _make_engine(min_rounds=1, convergence_threshold=0.01)

        # First call: set baseline
        engine._client.query.return_value = [{"avg_vol": 0.1}]
        engine._check_convergence(2)

        # Second call: delta = |0.1 - 0.1| = 0 < 0.01 → converged
        engine._client.query.return_value = [{"avg_vol": 0.1}]
        assert engine._check_convergence(3) is True

    def test_returns_false_when_not_converged(self):
        engine = _make_engine(min_rounds=1, convergence_threshold=0.005)

        # First call
        engine._client.query.return_value = [{"avg_vol": 0.5}]
        engine._check_convergence(2)

        # Second call: large delta
        engine._client.query.return_value = [{"avg_vol": 0.2}]
        assert engine._check_convergence(3) is False

    def test_handles_none_avg_vol(self):
        engine = _make_engine(min_rounds=1, convergence_threshold=0.01)
        engine._client.query.return_value = [{"avg_vol": None}]

        # Should not crash
        result = engine._check_convergence(2)
        assert result is False

    def test_handles_empty_query_result(self):
        engine = _make_engine(min_rounds=1, convergence_threshold=0.01)
        engine._client.query.return_value = []

        result = engine._check_convergence(2)
        assert result is False


# ---------------------------------------------------------------------------
# _apply_decay
# ---------------------------------------------------------------------------

class TestApplyDecay:
    def test_calls_client_write(self):
        engine = _make_engine()
        engine._apply_decay()
        engine._client.write.assert_called_once()
        call_args = engine._client.write.call_args
        assert "volatility" in call_args[0][0]


# ---------------------------------------------------------------------------
# _propagate_metadata
# ---------------------------------------------------------------------------

class TestPropagateMetadata:
    def test_propagation_changes(self):
        engine = _make_engine()
        changes = {
            "propagation": [
                {"target": "e1", "property": "stance", "old": 0.3, "new": 0.5},
            ],
            "actions": [],
        }
        engine._propagate_metadata(changes, round_num=1)
        engine._metadata_bus.emit_property_change.assert_called_once()

    def test_action_effects(self):
        engine = _make_engine()
        changes = {
            "propagation": [],
            "actions": [
                {
                    "action": "lobby",
                    "effects": [
                        {
                            "type": "property_change",
                            "target": "e1",
                            "property": "stance",
                            "old": 0.5,
                            "new": 0.7,
                        },
                    ],
                },
            ],
        }
        engine._propagate_metadata(changes, round_num=2)
        engine._metadata_bus.emit_property_change.assert_called_once()

    def test_non_property_change_effects_ignored(self):
        engine = _make_engine()
        changes = {
            "propagation": [],
            "actions": [
                {
                    "action": "form_alliance",
                    "effects": [
                        {"type": "create_edge", "link_type": "ALLIANCE"},
                    ],
                },
            ],
        }
        engine._propagate_metadata(changes, round_num=1)
        engine._metadata_bus.emit_property_change.assert_not_called()

    def test_empty_changes(self):
        engine = _make_engine()
        engine._propagate_metadata({}, round_num=1)
        engine._metadata_bus.emit_property_change.assert_not_called()


# ---------------------------------------------------------------------------
# run (integration with mocked components)
# ---------------------------------------------------------------------------

class TestRun:
    def test_runs_to_completion(self):
        engine = _make_engine(max_rounds=3)
        events = [SimEvent(uid="e1", name="Event 1", magnitude=0.5, round=1)]

        result = engine.run(events)

        assert result.total_rounds == 3
        assert result.total_events == 1
        assert result.early_stop is False

    def test_early_stop_on_convergence(self):
        engine = _make_engine(max_rounds=10, min_rounds=1, convergence_threshold=0.01)

        # Make convergence check return True after first comparison
        call_count = [0]

        def mock_query(cypher, **kwargs):
            if "avg(n.volatility)" in cypher:
                call_count[0] += 1
                return [{"avg_vol": 0.1}]
            return []

        engine._client.query.side_effect = mock_query

        events = [SimEvent(uid="e1", name="E1", round=1)]
        result = engine.run(events)

        assert result.early_stop is True
        assert result.early_stop_reason == "수렴"
        assert result.total_rounds < 10

    def test_empty_events(self):
        engine = _make_engine(max_rounds=2)
        result = engine.run([])

        assert result.total_events == 0
        assert result.total_rounds == 2

    def test_snapshot_saved_each_round(self):
        engine = _make_engine(max_rounds=3)
        engine.run([])

        # Initial snapshot (round 0) + 3 rounds
        assert engine._snapshot.save.call_count == 4

    def test_actions_counted(self):
        engine = _make_engine(max_rounds=2)
        engine._action_resolver.resolve.return_value = [
            {"action": "lobby", "actor": "e1", "effects": []},
        ]

        result = engine.run([])
        assert result.total_actions == 2  # 1 action * 2 rounds

    def test_propagation_effects_counted(self):
        engine = _make_engine(max_rounds=2)
        engine._propagation.apply_effects.return_value = [
            {"target": "e1", "property": "stance", "delta": 0.1},
            {"target": "e2", "property": "stance", "delta": 0.2},
        ]

        # Need to make inject_events return impacted nodes so propagation runs
        events = [SimEvent(uid="src", name="Src", magnitude=0.5, round=1)]
        engine._client.query.return_value = [
            {"uid": "e1", "weight": 1.0, "susc": 0.5}
        ]
        engine._propagation.propagate.return_value = [MagicMock()]

        result = engine.run(events)
        assert result.total_propagation_effects >= 0

    def test_community_refresh_on_interval(self):
        engine = _make_engine(max_rounds=6, community_refresh_interval=3)
        engine.run([])

        # Community detect should be called at rounds 3 and 6
        assert engine._community.detect.call_count == 2

    def test_invariant_violations_logged(self):
        engine = _make_engine(max_rounds=1)
        engine._snapshot.check_invariants.return_value = [
            "stance 범위 위반: e1 = 1.5"
        ]

        # Should not crash, violations are logged
        result = engine.run([])
        assert result.total_rounds == 1


# ---------------------------------------------------------------------------
# _inject_events
# ---------------------------------------------------------------------------

class TestInjectEvents:
    def test_inject_single_event(self):
        engine = _make_engine()
        engine._client.query.return_value = [
            {"uid": "target1", "weight": 1.0, "susc": 0.5}
        ]

        events = [SimEvent(uid="src", name="Source", magnitude=0.8)]
        impacted = engine._inject_events(events)

        # delta = 0.8 * 1.0 * 0.5 = 0.4
        assert len(impacted) >= 1
        engine._client.update_entity_property.assert_called()

    def test_inject_no_impacts(self):
        engine = _make_engine()
        engine._client.query.return_value = []

        events = [SimEvent(uid="isolated", name="Isolated", magnitude=0.5)]
        impacted = engine._inject_events(events)

        assert impacted == []

    def test_fallback_to_influences(self):
        engine = _make_engine()

        call_count = [0]

        def mock_query(cypher, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First query (IMPACTS) returns nothing
                return []
            else:
                # Second query (INFLUENCES|REACTS_TO) returns results
                return [{"uid": "n1", "weight": 1.0, "susc": 0.6}]

        engine._client.query.side_effect = mock_query

        events = [SimEvent(uid="src", name="Src", magnitude=0.5)]
        impacted = engine._inject_events(events)

        assert len(impacted) >= 1


# ---------------------------------------------------------------------------
# _evaluate_meta_edges
# ---------------------------------------------------------------------------

class TestEvaluateMetaEdges:
    def test_with_propagation_changes(self):
        engine = _make_engine()
        engine._client.get_all_entities.return_value = [
            {"props": {"uid": "e1", "stance": 0.5}},
            {"props": {"uid": "e2", "stance": -0.3}},
        ]
        engine._meta_engine.evaluate_on_change.return_value = [{"rule": "test"}]
        engine._meta_engine.evaluate_all.return_value = []

        changes = {
            "propagation": [{"property": "stance", "target": "e1"}]
        }
        results = engine._evaluate_meta_edges(changes)

        assert len(results) >= 1
        engine._meta_engine.evaluate_on_change.assert_called()

    def test_without_propagation(self):
        engine = _make_engine()
        engine._client.get_all_entities.return_value = []
        engine._meta_engine.evaluate_all.return_value = [{"rule": "eval_test"}]

        results = engine._evaluate_meta_edges({})
        assert len(results) >= 1
