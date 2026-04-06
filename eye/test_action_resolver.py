"""Tests for simulation/action_resolver.py — action resolution and effects."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from simulation.action_resolver import ActionResolver


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_effect(**kwargs):
    """Create a mock Effect object."""
    defaults = {
        "target": "self",
        "property": "stance",
        "operation": "add",
        "value": 0.1,
        "link_type": "",
        "relation": "",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_action(**kwargs):
    """Create a mock ActionType object."""
    defaults = {
        "name": "test_action",
        "actor_types": ["Actor"],
        "target_types": [],
        "preconditions": [],
        "effects": [],
        "cooldown": 1,
        "priority": 5,
        "description": "test",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_resolver(
    entities=None,
    actions=None,
    entity_props=None,
    max_actions=1,
):
    """Create an ActionResolver with mocked dependencies."""
    client = MagicMock()

    # get_entity returns entity properties
    if entity_props:
        client.get_entity.side_effect = lambda uid: entity_props.get(uid)
    else:
        client.get_entity.return_value = {
            "uid": "e1",
            "stance": 0.5,
            "volatility": 0.3,
            "activity_level": 0.5,
            "susceptibility": 0.5,
            "influence_score": 0.5,
        }

    # query for active entities
    client.query.return_value = entities or []

    registry = MagicMock()
    registry.get_actions_for_type.return_value = actions or []
    registry.check_cooldown.return_value = True
    registry.evaluate_preconditions.return_value = (True, [])

    return ActionResolver(client=client, registry=registry, max_actions_per_entity=max_actions)


# ---------------------------------------------------------------------------
# _resolve_value
# ---------------------------------------------------------------------------

class TestResolveValue:
    def _resolver(self):
        return _make_resolver()

    def test_int_value(self):
        r = self._resolver()
        assert r._resolve_value(5, {}) == 5.0

    def test_float_value(self):
        r = self._resolver()
        assert r._resolve_value(0.3, {}) == 0.3

    def test_string_number(self):
        r = self._resolver()
        assert r._resolve_value("0.5", {}) == 0.5

    def test_self_reference(self):
        r = self._resolver()
        entity = {"influence_score": 0.8}
        result = r._resolve_value("self.influence_score", entity)
        assert result == pytest.approx(0.8)

    def test_self_reference_with_multiplier(self):
        r = self._resolver()
        entity = {"influence_score": 0.5}
        result = r._resolve_value("self.influence_score * 0.3", entity)
        assert result == pytest.approx(0.15)

    def test_self_reference_missing_property(self):
        r = self._resolver()
        entity = {}
        result = r._resolve_value("self.missing_prop", entity)
        assert result == pytest.approx(0.5)  # default

    def test_invalid_string(self):
        r = self._resolver()
        assert r._resolve_value("not_a_number", {}) == 0.0

    def test_none_value(self):
        r = self._resolver()
        assert r._resolve_value(None, {}) == 0.0

    def test_list_value(self):
        r = self._resolver()
        assert r._resolve_value([1, 2, 3], {}) == 0.0


# ---------------------------------------------------------------------------
# _apply_property_change
# ---------------------------------------------------------------------------

class TestApplyPropertyChange:
    def test_add_operation(self):
        resolver = _make_resolver()
        effect = _make_effect(operation="add", property="stance", value=0.2)
        entity = {"stance": 0.5}
        effects_log = []

        resolver._apply_property_change("e1", effect, entity, effects_log)

        resolver._client.update_entity_property.assert_called_once()
        assert len(effects_log) == 1
        assert effects_log[0]["old"] == pytest.approx(0.5)
        assert effects_log[0]["new"] == pytest.approx(0.7)

    def test_subtract_operation(self):
        resolver = _make_resolver()
        effect = _make_effect(operation="subtract", property="stance", value=0.3)
        entity = {"stance": 0.5}
        effects_log = []

        resolver._apply_property_change("e1", effect, entity, effects_log)

        assert effects_log[0]["new"] == pytest.approx(0.2)

    def test_multiply_operation(self):
        resolver = _make_resolver()
        effect = _make_effect(operation="multiply", property="volatility", value=2.0)
        entity = {"volatility": 0.3}

        # Override get_entity to return volatility
        resolver._client.get_entity.return_value = {"volatility": 0.3}

        effects_log = []
        resolver._apply_property_change("e1", effect, entity, effects_log)

        assert effects_log[0]["new"] == pytest.approx(0.6)

    def test_set_operation(self):
        resolver = _make_resolver()
        effect = _make_effect(operation="set", property="stance", value=0.0)
        entity = {}
        effects_log = []

        resolver._apply_property_change("e1", effect, entity, effects_log)

        assert effects_log[0]["new"] == pytest.approx(0.0)

    def test_stance_clamped_upper(self):
        resolver = _make_resolver()
        resolver._client.get_entity.return_value = {"stance": 0.9}
        effect = _make_effect(operation="add", property="stance", value=0.5)
        effects_log = []

        resolver._apply_property_change("e1", effect, {}, effects_log)

        assert effects_log[0]["new"] == pytest.approx(1.0)

    def test_stance_clamped_lower(self):
        resolver = _make_resolver()
        resolver._client.get_entity.return_value = {"stance": -0.8}
        effect = _make_effect(operation="subtract", property="stance", value=0.5)
        effects_log = []

        resolver._apply_property_change("e1", effect, {}, effects_log)

        assert effects_log[0]["new"] == pytest.approx(-1.0)

    def test_volatility_clamped_0_to_1(self):
        resolver = _make_resolver()
        resolver._client.get_entity.return_value = {"volatility": 0.9}
        effect = _make_effect(operation="add", property="volatility", value=0.5)
        effects_log = []

        resolver._apply_property_change("e1", effect, {}, effects_log)

        assert effects_log[0]["new"] == pytest.approx(1.0)

    def test_no_effect_for_missing_entity(self):
        resolver = _make_resolver()
        resolver._client.get_entity.return_value = None
        effect = _make_effect()
        effects_log = []

        resolver._apply_property_change("missing", effect, {}, effects_log)
        assert effects_log == []

    def test_unknown_operation_skipped(self):
        resolver = _make_resolver()
        effect = _make_effect(operation="unknown_op")
        effects_log = []

        resolver._apply_property_change("e1", effect, {}, effects_log)
        assert effects_log == []


# ---------------------------------------------------------------------------
# _apply_effects
# ---------------------------------------------------------------------------

class TestApplyEffects:
    def test_self_target(self):
        resolver = _make_resolver()
        action = _make_action(
            effects=[_make_effect(target="self", operation="add", value=0.1)]
        )
        entity = {"uid": "e1", "stance": 0.5}

        effects = resolver._apply_effects(action, entity, round_num=1)
        assert len(effects) == 1
        assert effects[0]["type"] == "property_change"

    def test_create_edge_effect(self):
        resolver = _make_resolver()
        action = _make_action(
            effects=[_make_effect(
                operation="create_edge",
                link_type="ALLIANCE",
                target="self",
            )]
        )
        entity = {"uid": "e1"}

        effects = resolver._apply_effects(action, entity, round_num=1)
        assert len(effects) == 1
        assert effects[0]["type"] == "create_edge"
        assert effects[0]["link_type"] == "ALLIANCE"

    def test_expire_edge_effect(self):
        resolver = _make_resolver()
        action = _make_action(
            effects=[_make_effect(
                operation="expire_edge",
                relation="ALLIED_WITH",
                target="self",
            )]
        )
        entity = {"uid": "e1"}

        effects = resolver._apply_effects(action, entity, round_num=5)
        assert len(effects) == 1
        assert effects[0]["type"] == "expire_edge"
        assert effects[0]["round"] == 5

    def test_multiple_effects(self):
        resolver = _make_resolver()
        action = _make_action(
            effects=[
                _make_effect(target="self", operation="add", value=0.1),
                _make_effect(
                    target="self", operation="create_edge", link_type="X"
                ),
            ]
        )
        entity = {"uid": "e1", "stance": 0.5}

        effects = resolver._apply_effects(action, entity, round_num=1)
        assert len(effects) == 2


# ---------------------------------------------------------------------------
# resolve (full flow)
# ---------------------------------------------------------------------------

class TestResolve:
    def test_no_active_entities(self):
        resolver = _make_resolver(entities=[])
        log = resolver.resolve(round_num=1)
        assert log == []

    def test_no_actions_for_type(self):
        resolver = _make_resolver(
            entities=[{"props": {"uid": "e1", "object_type": "Actor", "activity_level": 0.5}}],
            actions=[],
        )
        log = resolver.resolve(round_num=1)
        assert log == []

    def test_cooldown_prevents_action(self):
        action = _make_action(name="lobby")
        resolver = _make_resolver(
            entities=[{"props": {"uid": "e1", "object_type": "Actor", "activity_level": 0.5}}],
            actions=[action],
        )
        # Override cooldown check to fail
        resolver._registry.check_cooldown.return_value = False

        log = resolver.resolve(round_num=1)
        assert log == []

    def test_precondition_failure_prevents_action(self):
        action = _make_action(name="lobby")
        resolver = _make_resolver(
            entities=[{"props": {"uid": "e1", "object_type": "Actor", "activity_level": 0.5}}],
            actions=[action],
        )
        resolver._registry.evaluate_preconditions.return_value = (False, [{"met": False}])

        log = resolver.resolve(round_num=1)
        assert log == []

    def test_successful_action_execution(self):
        action = _make_action(
            name="lobby",
            effects=[_make_effect(target="self", operation="add", value=0.1)],
        )
        resolver = _make_resolver(
            entities=[{"props": {
                "uid": "e1",
                "name": "Entity 1",
                "object_type": "Actor",
                "activity_level": 0.5,
                "influence_score": 0.7,
            }}],
            actions=[action],
        )

        log = resolver.resolve(round_num=1)
        assert len(log) == 1
        assert log[0]["action"] == "lobby"
        assert log[0]["actor"] == "e1"
        assert log[0]["round"] == 1
        resolver._registry.record_action.assert_called_once_with("e1", "lobby", 1)

    def test_max_actions_per_entity(self):
        action1 = _make_action(name="act1", effects=[])
        action2 = _make_action(name="act2", effects=[])
        resolver = _make_resolver(
            entities=[{"props": {"uid": "e1", "object_type": "Actor", "activity_level": 0.5}}],
            actions=[action1, action2],
            max_actions=1,
        )

        log = resolver.resolve(round_num=1)
        assert len(log) == 1  # Only one action per entity


# ---------------------------------------------------------------------------
# _graph_query
# ---------------------------------------------------------------------------

class TestGraphQuery:
    def test_shortest_path(self):
        resolver = _make_resolver()
        resolver._client.query.return_value = [{"dist": 3}]

        result = resolver._graph_query("shortest_path", "a", "b")
        assert result == 3

    def test_shortest_path_no_result(self):
        resolver = _make_resolver()
        resolver._client.query.return_value = []

        result = resolver._graph_query("shortest_path", "a", "b")
        assert result is None

    def test_relationship_check_with_type(self):
        resolver = _make_resolver()
        resolver._client.query.return_value = [{"cnt": 1}]

        result = resolver._graph_query(
            "(a)-[:INFLUENCES]->(b)", "src", "tgt"
        )
        assert result is True

    def test_relationship_check_no_match(self):
        resolver = _make_resolver()
        resolver._client.query.return_value = [{"cnt": 0}]

        result = resolver._graph_query(
            "(a)-[:INFLUENCES]->(b)", "src", "tgt"
        )
        assert result is False

    def test_generic_relationship_check(self):
        resolver = _make_resolver()
        resolver._client.query.return_value = [{"cnt": 2}]

        result = resolver._graph_query("some_pattern", "src", "tgt")
        assert result is True
