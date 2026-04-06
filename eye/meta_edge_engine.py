"""메타엣지 엔진 — YAML 규칙 파서 + 평가 엔진"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from utils.config import load_yaml, project_root

logger = logging.getLogger("comadeye")


@dataclass
class MetaEdgeCondition:
    """메타엣지 규칙의 개별 조건."""
    type: str  # property_comparison | relationship_exists | community | proximity | aggregate | temporal
    left: str = ""
    right: str = ""
    operator: str = ""
    compare: str = ""
    value: Any = None
    pattern: str = ""
    condition: str = ""


@dataclass
class MetaEdgeAction:
    """메타엣지 규칙의 효과."""
    type: str  # create_edge | remove_edge | modify_property | trigger_event
    link_type: str = ""
    source: str = ""
    target: str = ""
    property: str = ""
    operation: str = ""
    value: Any = None
    blend_factor: float = 0.0
    event: str = ""
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetaEdgeRule:
    """메타엣지 규칙."""
    name: str
    description: str = ""
    trigger: str = "evaluate"  # on_change | evaluate
    watch: list[str] = field(default_factory=list)
    priority: int = 5
    conditions: list[MetaEdgeCondition] = field(default_factory=list)
    actions: list[MetaEdgeAction] = field(default_factory=list)


class MetaEdgeEngine:
    """YAML 기반 메타엣지 규칙 평가 엔진."""

    def __init__(self, rules_path: str | None = None):
        path = rules_path or str(project_root() / "config" / "meta_edges.yaml")
        raw = load_yaml(path)
        self._rules = self._parse_rules(raw)
        self._fired_log: list[dict[str, Any]] = []

    @property
    def rules(self) -> list[MetaEdgeRule]:
        return self._rules

    @property
    def fired_log(self) -> list[dict[str, Any]]:
        return self._fired_log

    def _parse_rules(self, raw: dict[str, Any]) -> list[MetaEdgeRule]:
        """YAML → MetaEdgeRule 객체 리스트."""
        rules = []
        for name, data in raw.get("rules", {}).items():
            conditions = [
                MetaEdgeCondition(**c)
                for c in data.get("conditions", [])
            ]
            actions = [
                MetaEdgeAction(**a)
                for a in data.get("actions", [])
            ]
            rule = MetaEdgeRule(
                name=name,
                description=data.get("description", ""),
                trigger=data.get("trigger", "evaluate"),
                watch=data.get("watch", []),
                priority=data.get("priority", 5),
                conditions=conditions,
                actions=actions,
            )
            rules.append(rule)
        return sorted(rules, key=lambda r: -r.priority)

    def evaluate_on_change(
        self,
        changed_property: str,
        source_entity: dict[str, Any],
        target_entities: list[dict[str, Any]],
        graph_query_fn: Any = None,
    ) -> list[dict[str, Any]]:
        """속성 변경에 의해 트리거되는 규칙을 평가한다."""
        results = []
        on_change_rules = [
            r for r in self._rules
            if r.trigger == "on_change" and changed_property in r.watch
        ]
        for rule in on_change_rules:
            for target in target_entities:
                if self._evaluate_conditions(
                    rule.conditions, source_entity, target, graph_query_fn
                ):
                    effects = self._apply_actions(
                        rule.actions, source_entity, target
                    )
                    result = {
                        "rule": rule.name,
                        "source": source_entity.get("uid", ""),
                        "target": target.get("uid", ""),
                        "effects": effects,
                    }
                    results.append(result)
                    self._fired_log.append(result)
        return results

    def evaluate_all(
        self,
        entities: list[dict[str, Any]],
        graph_query_fn: Any = None,
    ) -> list[dict[str, Any]]:
        """전체 활성 규칙(evaluate 트리거)을 평가한다."""
        results = []
        eval_rules = [r for r in self._rules if r.trigger == "evaluate"]
        for rule in eval_rules:
            for i, source in enumerate(entities):
                for target in entities[i + 1:]:
                    if self._evaluate_conditions(
                        rule.conditions, source, target, graph_query_fn
                    ):
                        effects = self._apply_actions(
                            rule.actions, source, target
                        )
                        result = {
                            "rule": rule.name,
                            "source": source.get("uid", ""),
                            "target": target.get("uid", ""),
                            "effects": effects,
                        }
                        results.append(result)
                        self._fired_log.append(result)
        return results

    def _evaluate_conditions(
        self,
        conditions: list[MetaEdgeCondition],
        source: dict[str, Any],
        target: dict[str, Any],
        graph_query_fn: Any = None,
    ) -> bool:
        """모든 조건을 AND로 평가한다."""
        for cond in conditions:
            if not self._evaluate_single_condition(
                cond, source, target, graph_query_fn
            ):
                return False
        return True

    def _evaluate_single_condition(
        self,
        cond: MetaEdgeCondition,
        source: dict[str, Any],
        target: dict[str, Any],
        graph_query_fn: Any = None,
    ) -> bool:
        """개별 조건을 평가한다."""
        if cond.type == "property_comparison":
            return self._eval_property_comparison(cond, source, target)
        elif cond.type == "relationship_exists":
            if graph_query_fn:
                return self._eval_relationship_exists(
                    cond, source, target, graph_query_fn
                )
            return True  # 그래프 쿼리 없으면 True 가정
        elif cond.type == "community":
            return self._eval_community(cond, source, target)
        else:
            logger.debug(f"미지원 조건 타입: {cond.type}")
            return True

    def _eval_property_comparison(
        self,
        cond: MetaEdgeCondition,
        source: dict[str, Any],
        target: dict[str, Any],
    ) -> bool:
        """속성 비교 조건을 평가한다."""
        left_val = self._resolve_value(cond.left, source, target)
        compare = cond.compare or cond.operator
        threshold = cond.value

        if left_val is None or threshold is None:
            return False

        if compare == "in":
            return left_val in threshold
        elif compare == "==":
            return left_val == threshold
        elif compare == "!=":
            return left_val != threshold
        elif compare == ">":
            return float(left_val) > float(threshold)
        elif compare == "<":
            return float(left_val) < float(threshold)
        elif compare == ">=":
            return float(left_val) >= float(threshold)
        elif compare == "<=":
            return float(left_val) <= float(threshold)
        return False

    def _eval_relationship_exists(
        self,
        cond: MetaEdgeCondition,
        source: dict[str, Any],
        target: dict[str, Any],
        graph_query_fn: Any,
    ) -> bool:
        """관계 존재 여부를 평가한다."""
        exists = cond.condition == "exists"
        # 단순화: graph_query_fn에 패턴과 source/target uid를 전달
        result = graph_query_fn(
            cond.pattern,
            source.get("uid", ""),
            target.get("uid", ""),
        )
        return bool(result) == exists

    def _eval_community(
        self,
        cond: MetaEdgeCondition,
        source: dict[str, Any],
        target: dict[str, Any],
    ) -> bool:
        """커뮤니티 조건을 평가한다."""
        src_comm = source.get("community_id", "")
        tgt_comm = target.get("community_id", "")
        if "==" in cond.condition:
            return src_comm == tgt_comm and src_comm != ""
        elif "!=" in cond.condition:
            return src_comm != tgt_comm
        return False

    def _resolve_value(
        self,
        expr: str,
        source: dict[str, Any],
        target: dict[str, Any],
    ) -> Any:
        """표현식을 실제 값으로 해석한다."""
        if not expr:
            return None

        # abs(source.X - target.Y) 패턴
        if expr.startswith("abs("):
            inner = expr[4:-1]
            parts = inner.split(" - ")
            if len(parts) == 2:
                a = self._resolve_value(parts[0].strip(), source, target)
                b = self._resolve_value(parts[1].strip(), source, target)
                if a is not None and b is not None:
                    return abs(float(a) - float(b))

        # source.X - target.Y 패턴
        if " - " in expr:
            parts = expr.split(" - ")
            if len(parts) == 2:
                a = self._resolve_value(parts[0].strip(), source, target)
                b = self._resolve_value(parts[1].strip(), source, target)
                if a is not None and b is not None:
                    return float(a) - float(b)

        # source.property / target.property
        if expr.startswith("source."):
            prop = expr[7:]
            return source.get(prop)
        elif expr.startswith("target."):
            prop = expr[7:]
            return target.get(prop)

        # 리터럴
        try:
            return float(expr)
        except (ValueError, TypeError):
            return expr

    def _apply_actions(
        self,
        actions: list[MetaEdgeAction],
        source: dict[str, Any],
        target: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """규칙의 효과를 반환한다 (실제 적용은 호출자가 수행)."""
        effects = []
        for action in actions:
            effect: dict[str, Any] = {
                "type": action.type,
                "source": source.get("uid", ""),
                "target": target.get("uid", ""),
            }
            if action.type == "create_edge":
                effect["link_type"] = action.link_type
                effect["properties"] = action.properties
            elif action.type == "modify_property":
                effect["property"] = action.property
                effect["operation"] = action.operation
                effect["value"] = self._resolve_value(
                    str(action.value), source, target
                )
            elif action.type == "trigger_event":
                effect["event"] = action.value
            effects.append(effect)
        return effects

    def reset_log(self) -> None:
        self._fired_log.clear()
