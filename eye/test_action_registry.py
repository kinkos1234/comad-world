"""Tests for ontology/action_registry.py — Action type registry + precondition evaluation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ontology.schema import Precondition
from ontology.action_registry import ActionRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_YAML = {
    "actions": {
        "persuade": {
            "actor_types": ["Actor"],
            "target_types": ["Actor"],
            "preconditions": [
                {
                    "type": "property",
                    "target": "self",
                    "property": "influence_score",
                    "operator": ">",
                    "value": 0.3,
                },
                {
                    "type": "property",
                    "comparison": "abs(self.stance - target.stance)",
                    "operator": "<",
                    "value": 0.8,
                },
            ],
            "effects": [
                {
                    "target": "target",
                    "property": "stance",
                    "operation": "blend",
                    "blend_factor": 0.3,
                }
            ],
            "cooldown": 2,
            "priority": 8,
            "description": "설득 행동",
        },
        "mobilize": {
            "actor_types": ["Actor", "Event"],
            "target_types": ["Actor"],
            "preconditions": [
                {
                    "type": "community",
                    "condition": "==",
                },
                {
                    "type": "proximity",
                    "max_hops": 3,
                },
            ],
            "effects": [
                {
                    "target": "target",
                    "property": "volatility",
                    "operation": "add",
                    "value": 0.1,
                }
            ],
            "cooldown": 3,
            "priority": 6,
            "description": "동원 행동",
        },
        "observe": {
            "actor_types": ["Environment"],
            "target_types": ["Actor"],
            "preconditions": [
                {
                    "type": "relationship",
                    "pattern": "INFLUENCES",
                    "condition": "exists",
                },
            ],
            "effects": [],
            "cooldown": 1,
            "priority": 3,
            "description": "관찰 행동",
        },
    }
}


@pytest.fixture
def registry():
    with patch("ontology.action_registry.load_yaml", return_value=SAMPLE_YAML):
        return ActionRegistry(actions_path="/fake/path.yaml")


# ---------------------------------------------------------------------------
# Parsing tests
# ---------------------------------------------------------------------------

class TestParsing:
    def test_action_count(self, registry):
        assert len(registry.actions) == 3

    def test_action_types(self, registry):
        assert "persuade" in registry.actions
        assert "mobilize" in registry.actions
        assert "observe" in registry.actions

    def test_preconditions_parsed(self, registry):
        assert len(registry.actions["persuade"].preconditions) == 2
        assert registry.actions["persuade"].preconditions[0].type == "property"

    def test_effects_parsed(self, registry):
        assert len(registry.actions["persuade"].effects) == 1
        assert registry.actions["persuade"].effects[0].operation == "blend"

    def test_cooldown_and_priority(self, registry):
        assert registry.actions["persuade"].cooldown == 2
        assert registry.actions["persuade"].priority == 8

    def test_empty_actions(self):
        with patch("ontology.action_registry.load_yaml", return_value={"actions": {}}):
            reg = ActionRegistry(actions_path="/fake")
        assert reg.actions == {}


# ---------------------------------------------------------------------------
# get_actions_for_type
# ---------------------------------------------------------------------------

class TestGetActionsForType:
    def test_actor_type(self, registry):
        actions = registry.get_actions_for_type("Actor")
        names = [a.name for a in actions]
        assert "persuade" in names
        assert "mobilize" in names
        assert "observe" not in names

    def test_sorted_by_priority_desc(self, registry):
        actions = registry.get_actions_for_type("Actor")
        priorities = [a.priority for a in actions]
        assert priorities == sorted(priorities, reverse=True)

    def test_environment_type(self, registry):
        actions = registry.get_actions_for_type("Environment")
        assert len(actions) == 1
        assert actions[0].name == "observe"

    def test_unknown_type(self, registry):
        assert registry.get_actions_for_type("Unknown") == []


# ---------------------------------------------------------------------------
# Cooldown
# ---------------------------------------------------------------------------

class TestCooldown:
    def test_initial_cooldown_ready(self, registry):
        assert registry.check_cooldown("e1", "persuade", 0) is True

    def test_cooldown_not_ready(self, registry):
        registry.record_action("e1", "persuade", 0)
        assert registry.check_cooldown("e1", "persuade", 1) is False

    def test_cooldown_ready_after_period(self, registry):
        registry.record_action("e1", "persuade", 0)
        # persuade cooldown = 2
        assert registry.check_cooldown("e1", "persuade", 2) is True

    def test_cooldown_unknown_action(self, registry):
        assert registry.check_cooldown("e1", "nonexistent", 0) is False

    def test_record_action(self, registry):
        registry.record_action("e1", "mobilize", 5)
        # mobilize cooldown = 3
        assert registry.check_cooldown("e1", "mobilize", 7) is False
        assert registry.check_cooldown("e1", "mobilize", 8) is True


# ---------------------------------------------------------------------------
# evaluate_preconditions — property type
# ---------------------------------------------------------------------------

class TestEvaluatePropertyPreconditions:
    def test_property_met(self, registry):
        action = registry.actions["persuade"]
        entity = {"influence_score": 0.5, "stance": 0.3}
        target = {"stance": 0.6}
        met, results = registry.evaluate_preconditions(action, entity, target)
        assert met is True
        assert all(r["met"] for r in results)

    def test_property_not_met(self, registry):
        action = registry.actions["persuade"]
        entity = {"influence_score": 0.1, "stance": 0.3}
        target = {"stance": 0.6}
        met, results = registry.evaluate_preconditions(action, entity, target)
        assert met is False

    def test_property_missing(self, registry):
        action = registry.actions["persuade"]
        entity = {}
        target = {"stance": 0.5}
        met, _ = registry.evaluate_preconditions(action, entity, target)
        assert met is False


# ---------------------------------------------------------------------------
# evaluate_preconditions — community type
# ---------------------------------------------------------------------------

class TestEvaluateCommunityPreconditions:
    def test_same_community(self, registry):
        action = registry.actions["mobilize"]
        entity = {"community_id": "C0_1", "uid": "a"}
        target = {"community_id": "C0_1", "uid": "b"}
        # proximity needs graph_query_fn
        query_fn = MagicMock(return_value=2)
        met, results = registry.evaluate_preconditions(action, entity, target, query_fn)
        assert met is True

    def test_different_community(self, registry):
        action = registry.actions["mobilize"]
        entity = {"community_id": "C0_1", "uid": "a"}
        target = {"community_id": "C0_2", "uid": "b"}
        query_fn = MagicMock(return_value=1)
        met, _ = registry.evaluate_preconditions(action, entity, target, query_fn)
        assert met is False


# ---------------------------------------------------------------------------
# evaluate_preconditions — relationship type
# ---------------------------------------------------------------------------

class TestEvaluateRelationshipPreconditions:
    def test_relationship_exists(self, registry):
        action = registry.actions["observe"]
        entity = {"uid": "a"}
        target = {"uid": "b"}
        query_fn = MagicMock(return_value=[{"exists": True}])
        met, _ = registry.evaluate_preconditions(action, entity, target, query_fn)
        assert met is True

    def test_relationship_not_exists(self, registry):
        action = registry.actions["observe"]
        entity = {"uid": "a"}
        target = {"uid": "b"}
        query_fn = MagicMock(return_value=[])
        met, _ = registry.evaluate_preconditions(action, entity, target, query_fn)
        assert met is False

    def test_relationship_no_query_fn(self, registry):
        action = registry.actions["observe"]
        entity = {"uid": "a"}
        target = {"uid": "b"}
        met, _ = registry.evaluate_preconditions(action, entity, target)
        assert met is True  # defaults to True when no query fn


# ---------------------------------------------------------------------------
# evaluate_preconditions — proximity type
# ---------------------------------------------------------------------------

class TestEvaluateProximityPreconditions:
    def test_proximity_within_hops(self, registry):
        action = registry.actions["mobilize"]
        entity = {"community_id": "C0_1", "uid": "a"}
        target = {"community_id": "C0_1", "uid": "b"}
        query_fn = MagicMock(return_value=2)  # distance=2, max_hops=3
        met, _ = registry.evaluate_preconditions(action, entity, target, query_fn)
        assert met is True

    def test_proximity_too_far(self, registry):
        action = registry.actions["mobilize"]
        entity = {"community_id": "C0_1", "uid": "a"}
        target = {"community_id": "C0_1", "uid": "b"}
        query_fn = MagicMock(return_value=5)  # distance=5 > max_hops=3
        met, _ = registry.evaluate_preconditions(action, entity, target, query_fn)
        assert met is False

    def test_proximity_no_path(self, registry):
        action = registry.actions["mobilize"]
        entity = {"community_id": "C0_1", "uid": "a"}
        target = {"community_id": "C0_1", "uid": "b"}
        query_fn = MagicMock(return_value=None)
        met, _ = registry.evaluate_preconditions(action, entity, target, query_fn)
        assert met is False


# ---------------------------------------------------------------------------
# _eval_property operators
# ---------------------------------------------------------------------------

class TestEvalPropertyOperators:
    @pytest.mark.parametrize("op,val,threshold,expected", [
        (">", 5, 3, True),
        (">", 3, 5, False),
        ("<", 3, 5, True),
        ("<", 5, 3, False),
        (">=", 5, 5, True),
        (">=", 4, 5, False),
        ("<=", 5, 5, True),
        ("<=", 6, 5, False),
        ("==", 5, 5, True),
        ("==", 5, 6, False),
    ])
    def test_operators(self, registry, op, val, threshold, expected):
        pre = Precondition(type="property", target="self", property="x", operator=op, value=threshold)
        met, margin = registry._eval_property(pre, {"x": val}, None)
        assert met is expected

    def test_unknown_operator(self, registry):
        pre = Precondition(type="property", target="self", property="x", operator="??", value=5)
        met, _ = registry._eval_property(pre, {"x": 5}, None)
        assert met is False

    def test_target_property(self, registry):
        pre = Precondition(type="property", target="target", property="stance", operator=">", value=0.3)
        met, _ = registry._eval_property(pre, {}, {"stance": 0.5})
        assert met is True


# ---------------------------------------------------------------------------
# _resolve_comparison
# ---------------------------------------------------------------------------

class TestResolveComparison:
    def test_abs_expression(self, registry):
        val = registry._resolve_comparison(
            "abs(self.stance - target.stance)",
            {"stance": 0.8},
            {"stance": 0.2},
        )
        assert val == pytest.approx(0.6)

    def test_non_abs_returns_none(self, registry):
        val = registry._resolve_comparison(
            "self.stance + target.stance",
            {"stance": 0.5},
            {"stance": 0.5},
        )
        assert val is None

    def test_none_target(self, registry):
        val = registry._resolve_comparison(
            "abs(self.stance - target.stance)",
            {"stance": 0.5},
            None,
        )
        # target becomes {} → target.stance is None → returns None
        assert val is None


# ---------------------------------------------------------------------------
# _get_nested_value
# ---------------------------------------------------------------------------

class TestGetNestedValue:
    def test_self_path(self, registry):
        val = registry._get_nested_value("self.x", {"x": 42}, {})
        assert val == 42

    def test_target_path(self, registry):
        val = registry._get_nested_value("target.y", {}, {"y": "hello"})
        assert val == "hello"

    def test_unknown_prefix(self, registry):
        val = registry._get_nested_value("other.z", {"z": 1}, {"z": 2})
        assert val is None
