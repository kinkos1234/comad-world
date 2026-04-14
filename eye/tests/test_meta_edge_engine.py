"""Tests for ontology/meta_edge_engine.py — YAML rule parser + evaluation engine."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from comad_eye.ontology.meta_edge_engine import (
    MetaEdgeAction,
    MetaEdgeCondition,
    MetaEdgeEngine,
    MetaEdgeRule,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_YAML = {
    "rules": {
        "stance_proximity": {
            "description": "stance가 유사한 엔티티를 연결",
            "trigger": "evaluate",
            "watch": [],
            "priority": 8,
            "conditions": [
                {
                    "type": "property_comparison",
                    "left": "abs(source.stance - target.stance)",
                    "operator": "<",
                    "value": 0.3,
                }
            ],
            "actions": [
                {
                    "type": "create_edge",
                    "link_type": "SIMILAR_STANCE",
                    "properties": {"auto": True},
                }
            ],
        },
        "on_change_rule": {
            "description": "stance 변경 시 트리거",
            "trigger": "on_change",
            "watch": ["stance"],
            "priority": 5,
            "conditions": [
                {
                    "type": "community",
                    "condition": "==",
                }
            ],
            "actions": [
                {
                    "type": "modify_property",
                    "property": "volatility",
                    "operation": "add",
                    "value": "0.1",
                }
            ],
        },
        "low_priority": {
            "description": "낮은 우선순위",
            "trigger": "evaluate",
            "priority": 1,
            "conditions": [],
            "actions": [
                {
                    "type": "trigger_event",
                    "value": "test_event",
                }
            ],
        },
    }
}


@pytest.fixture
def engine():
    """Construct engine from sample YAML without touching the filesystem."""
    with patch("comad_eye.ontology.meta_edge_engine.load_yaml", return_value=SAMPLE_YAML):
        return MetaEdgeEngine(rules_path="/fake/path.yaml")


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------

class TestMetaEdgeDataclasses:
    def test_condition_defaults(self):
        c = MetaEdgeCondition(type="property_comparison")
        assert c.left == ""
        assert c.operator == ""
        assert c.value is None

    def test_action_defaults(self):
        a = MetaEdgeAction(type="create_edge")
        assert a.link_type == ""
        assert a.blend_factor == 0.0
        assert a.properties == {}

    def test_rule_defaults(self):
        r = MetaEdgeRule(name="test")
        assert r.trigger == "evaluate"
        assert r.priority == 5
        assert r.conditions == []
        assert r.actions == []


# ---------------------------------------------------------------------------
# Parsing tests
# ---------------------------------------------------------------------------

class TestParseRules:
    def test_rule_count(self, engine):
        assert len(engine.rules) == 3

    def test_sorted_by_priority_desc(self, engine):
        priorities = [r.priority for r in engine.rules]
        assert priorities == sorted(priorities, reverse=True)

    def test_conditions_parsed(self, engine):
        stance_rule = next(r for r in engine.rules if r.name == "stance_proximity")
        assert len(stance_rule.conditions) == 1
        assert stance_rule.conditions[0].type == "property_comparison"

    def test_actions_parsed(self, engine):
        stance_rule = next(r for r in engine.rules if r.name == "stance_proximity")
        assert len(stance_rule.actions) == 1
        assert stance_rule.actions[0].type == "create_edge"
        assert stance_rule.actions[0].link_type == "SIMILAR_STANCE"

    def test_empty_rules(self):
        with patch("comad_eye.ontology.meta_edge_engine.load_yaml", return_value={"rules": {}}):
            eng = MetaEdgeEngine(rules_path="/fake")
        assert eng.rules == []

    def test_no_rules_key(self):
        with patch("comad_eye.ontology.meta_edge_engine.load_yaml", return_value={}):
            eng = MetaEdgeEngine(rules_path="/fake")
        assert eng.rules == []


# ---------------------------------------------------------------------------
# _resolve_value tests
# ---------------------------------------------------------------------------

class TestResolveValue:
    def test_source_property(self, engine):
        val = engine._resolve_value("source.stance", {"stance": 0.5}, {})
        assert val == 0.5

    def test_target_property(self, engine):
        val = engine._resolve_value("target.stance", {}, {"stance": -0.3})
        assert val == pytest.approx(-0.3)

    def test_abs_expression(self, engine):
        val = engine._resolve_value(
            "abs(source.stance - target.stance)",
            {"stance": 0.8},
            {"stance": 0.2},
        )
        assert val == pytest.approx(0.6)

    def test_subtraction_expression(self, engine):
        val = engine._resolve_value(
            "source.x - target.y",
            {"x": 10},
            {"y": 3},
        )
        assert val == pytest.approx(7.0)

    def test_literal_number(self, engine):
        val = engine._resolve_value("0.5", {}, {})
        assert val == pytest.approx(0.5)

    def test_literal_string(self, engine):
        val = engine._resolve_value("hello", {}, {})
        assert val == "hello"

    def test_empty_expression(self, engine):
        val = engine._resolve_value("", {}, {})
        assert val is None

    def test_abs_with_none_value(self, engine):
        val = engine._resolve_value(
            "abs(source.missing - target.stance)",
            {},
            {"stance": 0.5},
        )
        # When a property is missing inside an abs() expression, the engine
        # cannot compute the numeric result.  It falls through all numeric
        # resolution paths and returns the raw expression string (not None).
        assert isinstance(val, str)


# ---------------------------------------------------------------------------
# _evaluate_single_condition tests
# ---------------------------------------------------------------------------

class TestEvaluateSingleCondition:
    def test_property_comparison_lt(self, engine):
        cond = MetaEdgeCondition(
            type="property_comparison",
            left="abs(source.stance - target.stance)",
            operator="<",
            value=0.3,
        )
        src = {"stance": 0.5}
        tgt = {"stance": 0.6}
        assert engine._evaluate_single_condition(cond, src, tgt) is True

    def test_property_comparison_fails(self, engine):
        cond = MetaEdgeCondition(
            type="property_comparison",
            left="abs(source.stance - target.stance)",
            operator="<",
            value=0.1,
        )
        src = {"stance": 0.8}
        tgt = {"stance": 0.2}
        assert engine._evaluate_single_condition(cond, src, tgt) is False

    def test_relationship_exists_with_query_fn(self, engine):
        cond = MetaEdgeCondition(
            type="relationship_exists",
            pattern="INFLUENCES",
            condition="exists",
        )
        query_fn = MagicMock(return_value=[{"exists": True}])
        src = {"uid": "a"}
        tgt = {"uid": "b"}
        result = engine._evaluate_single_condition(cond, src, tgt, query_fn)
        assert result is True
        query_fn.assert_called_once_with("INFLUENCES", "a", "b")

    def test_relationship_exists_no_query_fn(self, engine):
        cond = MetaEdgeCondition(
            type="relationship_exists",
            pattern="INFLUENCES",
            condition="exists",
        )
        result = engine._evaluate_single_condition(cond, {"uid": "a"}, {"uid": "b"})
        assert result is True  # assumes True when no query fn

    def test_community_equal(self, engine):
        cond = MetaEdgeCondition(type="community", condition="==")
        src = {"community_id": "C0_1"}
        tgt = {"community_id": "C0_1"}
        assert engine._evaluate_single_condition(cond, src, tgt) is True

    def test_community_equal_empty(self, engine):
        cond = MetaEdgeCondition(type="community", condition="==")
        src = {"community_id": ""}
        tgt = {"community_id": ""}
        assert engine._evaluate_single_condition(cond, src, tgt) is False

    def test_community_not_equal(self, engine):
        cond = MetaEdgeCondition(type="community", condition="!=")
        src = {"community_id": "C0_1"}
        tgt = {"community_id": "C0_2"}
        assert engine._evaluate_single_condition(cond, src, tgt) is True

    def test_unknown_condition_type_returns_true(self, engine):
        cond = MetaEdgeCondition(type="unknown_type")
        assert engine._evaluate_single_condition(cond, {}, {}) is True


# ---------------------------------------------------------------------------
# _eval_property_comparison operators
# ---------------------------------------------------------------------------

class TestPropertyComparisonOperators:
    @pytest.mark.parametrize("op,val,threshold,expected", [
        ("in", "a", ["a", "b"], True),
        ("in", "c", ["a", "b"], False),
        ("==", 5, 5, True),
        ("==", 5, 6, False),
        ("!=", 5, 6, True),
        ("!=", 5, 5, False),
        (">", 5, 3, True),
        (">", 3, 5, False),
        ("<", 3, 5, True),
        (">=", 5, 5, True),
        ("<=", 5, 5, True),
    ])
    def test_operators(self, engine, op, val, threshold, expected):
        cond = MetaEdgeCondition(
            type="property_comparison",
            left="source.x",
            compare=op,
            value=threshold,
        )
        assert engine._eval_property_comparison(cond, {"x": val}, {}) is expected

    def test_none_left_returns_false(self, engine):
        cond = MetaEdgeCondition(
            type="property_comparison",
            left="source.missing",
            compare="==",
            value=5,
        )
        assert engine._eval_property_comparison(cond, {}, {}) is False

    def test_unknown_operator_returns_false(self, engine):
        cond = MetaEdgeCondition(
            type="property_comparison",
            left="source.x",
            compare="?!",
            value=5,
        )
        assert engine._eval_property_comparison(cond, {"x": 5}, {}) is False


# ---------------------------------------------------------------------------
# _apply_actions tests
# ---------------------------------------------------------------------------

class TestApplyActions:
    def test_create_edge(self, engine):
        action = MetaEdgeAction(
            type="create_edge",
            link_type="TEST_EDGE",
            properties={"auto": True},
        )
        effects = engine._apply_actions([action], {"uid": "a"}, {"uid": "b"})
        assert len(effects) == 1
        assert effects[0]["type"] == "create_edge"
        assert effects[0]["link_type"] == "TEST_EDGE"
        assert effects[0]["properties"]["auto"] is True

    def test_modify_property(self, engine):
        action = MetaEdgeAction(
            type="modify_property",
            property="volatility",
            operation="add",
            value="0.1",
        )
        effects = engine._apply_actions([action], {"uid": "a"}, {"uid": "b"})
        assert effects[0]["type"] == "modify_property"
        assert effects[0]["property"] == "volatility"
        assert effects[0]["operation"] == "add"

    def test_trigger_event(self, engine):
        action = MetaEdgeAction(
            type="trigger_event",
            value="alert_event",
        )
        effects = engine._apply_actions([action], {"uid": "a"}, {"uid": "b"})
        assert effects[0]["type"] == "trigger_event"
        assert effects[0]["event"] == "alert_event"


# ---------------------------------------------------------------------------
# evaluate_all / evaluate_on_change
# ---------------------------------------------------------------------------

class TestEvaluateAll:
    def test_evaluate_all_with_matching_entities(self, engine):
        entities = [
            {"uid": "a", "stance": 0.5},
            {"uid": "b", "stance": 0.6},
        ]
        results = engine.evaluate_all(entities)
        # The low_priority rule has empty conditions (always true)
        # The stance_proximity rule should match (abs diff = 0.1 < 0.3)
        assert len(results) > 0
        assert all("rule" in r for r in results)

    def test_evaluate_all_single_entity_no_results(self, engine):
        results = engine.evaluate_all([{"uid": "a", "stance": 0.5}])
        assert results == []

    def test_evaluate_all_empty(self, engine):
        results = engine.evaluate_all([])
        assert results == []


class TestEvaluateOnChange:
    def test_on_change_fires_for_watched_property(self, engine):
        src = {"uid": "a", "community_id": "C0_1"}
        targets = [{"uid": "b", "community_id": "C0_1"}]
        results = engine.evaluate_on_change("stance", src, targets)
        assert len(results) == 1
        assert results[0]["rule"] == "on_change_rule"

    def test_on_change_skips_unwatched_property(self, engine):
        src = {"uid": "a", "community_id": "C0_1"}
        targets = [{"uid": "b", "community_id": "C0_1"}]
        results = engine.evaluate_on_change("volatility", src, targets)
        assert results == []

    def test_on_change_condition_not_met(self, engine):
        src = {"uid": "a", "community_id": "C0_1"}
        targets = [{"uid": "b", "community_id": "C0_2"}]  # different community
        results = engine.evaluate_on_change("stance", src, targets)
        assert results == []


# ---------------------------------------------------------------------------
# Fired log / reset
# ---------------------------------------------------------------------------

class TestFiredLog:
    def test_fired_log_accumulates(self, engine):
        entities = [
            {"uid": "a", "stance": 0.5},
            {"uid": "b", "stance": 0.6},
        ]
        engine.evaluate_all(entities)
        assert len(engine.fired_log) > 0

    def test_reset_log(self, engine):
        entities = [
            {"uid": "a", "stance": 0.5},
            {"uid": "b", "stance": 0.6},
        ]
        engine.evaluate_all(entities)
        engine.reset_log()
        assert engine.fired_log == []
