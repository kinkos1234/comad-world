"""Extended tests for simulation/propagation.py — BFS propagation engine."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from comad_eye.simulation.propagation import PropagationEffect, PropagationEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    client = MagicMock()
    client.get_neighbors = MagicMock(return_value=[])
    client.query = MagicMock(return_value=[])
    client.write = MagicMock()
    return client


@pytest.fixture
def engine(mock_client):
    with patch("simulation.propagation.load_yaml", return_value={
        "relationship_rules": {
            "INFLUENCES": {
                "inversion": False,
                "propagated_properties": ["stance"],
            },
            "OPPOSES": {
                "inversion": True,
                "propagated_properties": ["stance", "volatility"],
            },
        }
    }):
        return PropagationEngine(
            mock_client,
            decay=0.6,
            max_hops=3,
            min_threshold=0.01,
        )


@pytest.fixture
def engine_no_rules(mock_client):
    with patch("simulation.propagation.load_yaml", side_effect=FileNotFoundError):
        return PropagationEngine(mock_client)


# ---------------------------------------------------------------------------
# _load_rules tests
# ---------------------------------------------------------------------------

class TestLoadRules:
    def test_rules_loaded(self, engine):
        assert "INFLUENCES" in engine._rules
        assert "OPPOSES" in engine._rules

    def test_file_not_found_returns_empty(self, engine_no_rules):
        assert engine_no_rules._rules == {}


# ---------------------------------------------------------------------------
# propagate() tests
# ---------------------------------------------------------------------------

class TestPropagate:
    def test_empty_impacted_nodes(self, engine):
        effects = engine.propagate([])
        assert effects == []

    def test_no_neighbors(self, engine, mock_client):
        mock_client.get_neighbors.return_value = []
        effects = engine.propagate([("a", 0.5)])
        assert effects == []

    def test_single_hop_propagation(self, engine, mock_client):
        mock_client.get_neighbors.side_effect = [
            [  # neighbors of "a"
                {
                    "uid": "b",
                    "rel_type": "INFLUENCES",
                    "weight": 1.0,
                    "props": {"susceptibility": 0.5},
                },
            ],
            [],  # neighbors of "b"
        ]
        effects = engine.propagate([("a", 1.0)])
        assert len(effects) == 1
        assert effects[0].source_uid == "a"
        assert effects[0].target_uid == "b"
        assert effects[0].distance == 1
        # effect = 1.0 * 0.6 * 1.0 * 0.5 = 0.3
        assert effects[0].effect == pytest.approx(0.3)

    def test_multi_hop_propagation(self, engine, mock_client):
        mock_client.get_neighbors.side_effect = [
            [{"uid": "b", "rel_type": "INFLUENCES", "weight": 1.0,
              "props": {"susceptibility": 1.0}}],
            [{"uid": "c", "rel_type": "INFLUENCES", "weight": 1.0,
              "props": {"susceptibility": 1.0}}],
            [],
        ]
        effects = engine.propagate([("a", 1.0)])
        assert len(effects) == 2
        assert effects[0].distance == 1
        assert effects[1].distance == 2

    def test_max_hops_respected(self, engine, mock_client):
        # Chain: a -> b -> c -> d -> e (4 hops, max is 3)
        def neighbors_side_effect(uid, active_only=True):
            mapping = {
                "a": [{"uid": "b", "rel_type": "INFLUENCES", "weight": 1.0,
                       "props": {"susceptibility": 1.0}}],
                "b": [{"uid": "c", "rel_type": "INFLUENCES", "weight": 1.0,
                       "props": {"susceptibility": 1.0}}],
                "c": [{"uid": "d", "rel_type": "INFLUENCES", "weight": 1.0,
                       "props": {"susceptibility": 1.0}}],
                "d": [{"uid": "e", "rel_type": "INFLUENCES", "weight": 1.0,
                       "props": {"susceptibility": 1.0}}],
            }
            return mapping.get(uid, [])

        mock_client.get_neighbors.side_effect = neighbors_side_effect
        effects = engine.propagate([("a", 1.0)])
        max_dist = max(e.distance for e in effects) if effects else 0
        assert max_dist <= 3

    def test_inversion_rule(self, engine, mock_client):
        mock_client.get_neighbors.side_effect = [
            [{"uid": "b", "rel_type": "OPPOSES", "weight": 1.0,
              "props": {"susceptibility": 1.0}}],
            [],
        ]
        effects = engine.propagate([("a", 1.0)])
        # OPPOSES has inversion=True, propagated_properties=["stance", "volatility"]
        assert len(effects) == 2
        # Both effects should be negative due to inversion
        for eff in effects:
            assert eff.effect < 0

    def test_threshold_filtering(self, engine, mock_client):
        mock_client.get_neighbors.side_effect = [
            [{"uid": "b", "rel_type": "INFLUENCES", "weight": 0.01,
              "props": {"susceptibility": 0.01}}],
            [],
        ]
        effects = engine.propagate([("a", 0.01)])
        # 0.01 * 0.6 * 0.01 * 0.01 = very small, below threshold
        assert effects == []

    def test_visited_nodes_not_revisited(self, engine, mock_client):
        # b points back to a
        mock_client.get_neighbors.side_effect = [
            [{"uid": "b", "rel_type": "INFLUENCES", "weight": 1.0,
              "props": {"susceptibility": 1.0}}],
            [{"uid": "a", "rel_type": "INFLUENCES", "weight": 1.0,
              "props": {"susceptibility": 1.0}}],
        ]
        effects = engine.propagate([("a", 1.0)])
        target_uids = [e.target_uid for e in effects]
        assert "a" not in target_uids

    def test_default_susceptibility(self, engine, mock_client):
        mock_client.get_neighbors.side_effect = [
            [{"uid": "b", "rel_type": "INFLUENCES", "weight": 1.0,
              "props": {}}],  # no susceptibility key
            [],
        ]
        effects = engine.propagate([("a", 1.0)])
        # Default susceptibility = 0.5
        assert len(effects) == 1
        assert effects[0].effect == pytest.approx(1.0 * 0.6 * 1.0 * 0.5)

    def test_unknown_rel_type_no_inversion(self, engine, mock_client):
        mock_client.get_neighbors.side_effect = [
            [{"uid": "b", "rel_type": "UNKNOWN_REL", "weight": 1.0,
              "props": {"susceptibility": 1.0}}],
            [],
        ]
        effects = engine.propagate([("a", 1.0)])
        # Unknown rel type → no inversion, default propagated_properties=["stance"]
        assert len(effects) == 1
        assert effects[0].effect > 0
        assert effects[0].property == "stance"


# ---------------------------------------------------------------------------
# apply_effects() tests
# ---------------------------------------------------------------------------

class TestApplyEffects:
    def test_empty_effects(self, engine):
        result = engine.apply_effects([])
        assert result == []

    def test_stance_clamping(self, engine, mock_client):
        mock_client.query.return_value = [
            {"uid": "b", "props": {"stance": 0.9}},
        ]
        effects = [PropagationEffect(
            source_uid="a", target_uid="b",
            effect=0.5, distance=1, rel_type="INFLUENCES", property="stance",
        )]
        result = engine.apply_effects(effects)
        assert len(result) == 1
        assert result[0]["new"] == 1.0  # clamped to 1.0
        assert result[0]["old"] == 0.9

    def test_stance_clamping_lower(self, engine, mock_client):
        mock_client.query.return_value = [
            {"uid": "b", "props": {"stance": -0.9}},
        ]
        effects = [PropagationEffect(
            source_uid="a", target_uid="b",
            effect=-0.5, distance=1, rel_type="INFLUENCES", property="stance",
        )]
        result = engine.apply_effects(effects)
        assert result[0]["new"] == -1.0  # clamped to -1.0

    def test_volatility_clamping(self, engine, mock_client):
        mock_client.query.return_value = [
            {"uid": "b", "props": {"volatility": 0.8}},
        ]
        effects = [PropagationEffect(
            source_uid="a", target_uid="b",
            effect=0.5, distance=1, rel_type="INFLUENCES", property="volatility",
        )]
        result = engine.apply_effects(effects)
        assert result[0]["new"] == 1.0  # clamped to 1.0

    def test_other_property_no_clamp(self, engine, mock_client):
        mock_client.query.return_value = [
            {"uid": "b", "props": {"event_activation": 0.5}},
        ]
        effects = [PropagationEffect(
            source_uid="a", target_uid="b",
            effect=2.0, distance=1, rel_type="INFLUENCES", property="event_activation",
        )]
        result = engine.apply_effects(effects)
        assert result[0]["new"] == 2.5  # no clamping

    def test_entity_not_found_skipped(self, engine, mock_client):
        mock_client.query.return_value = []
        effects = [PropagationEffect(
            source_uid="a", target_uid="missing",
            effect=0.5, distance=1, rel_type="INFLUENCES",
        )]
        result = engine.apply_effects(effects)
        assert result == []

    def test_batch_write_by_property(self, engine, mock_client):
        mock_client.query.return_value = [
            {"uid": "b", "props": {"stance": 0.0, "volatility": 0.0}},
        ]
        effects = [
            PropagationEffect(
                source_uid="a", target_uid="b",
                effect=0.1, distance=1, rel_type="INFLUENCES", property="stance",
            ),
            PropagationEffect(
                source_uid="a", target_uid="b",
                effect=0.2, distance=1, rel_type="INFLUENCES", property="volatility",
            ),
        ]
        engine.apply_effects(effects)
        # Two writes: one for stance, one for volatility
        assert mock_client.write.call_count == 2

    def test_missing_property_default_zero(self, engine, mock_client):
        mock_client.query.return_value = [
            {"uid": "b", "props": {"uid": "b"}},  # has props but no stance key
        ]
        effects = [PropagationEffect(
            source_uid="a", target_uid="b",
            effect=0.3, distance=1, rel_type="INFLUENCES", property="stance",
        )]
        result = engine.apply_effects(effects)
        assert result[0]["old"] == 0.0
        assert result[0]["new"] == pytest.approx(0.3)
