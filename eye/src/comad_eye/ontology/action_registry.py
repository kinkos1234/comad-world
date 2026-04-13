"""Action 레지스트리 — Action Type YAML 파서 + 전제조건 평가"""

from __future__ import annotations

import logging
from typing import Any

from comad_eye.ontology.schema import ActionType, Effect, Precondition
from comad_eye.utils.config import load_yaml, project_root

logger = logging.getLogger("comadeye")


class ActionRegistry:
    """Action Type 레지스트리 + 전제조건 평가 엔진."""

    def __init__(self, actions_path: str | None = None):
        path = actions_path or str(project_root() / "config" / "action_types.yaml")
        raw = load_yaml(path)
        self._actions = self._parse_actions(raw)
        self._cooldown_tracker: dict[str, dict[str, int]] = {}

    @property
    def actions(self) -> dict[str, ActionType]:
        return self._actions

    def _parse_actions(self, raw: dict[str, Any]) -> dict[str, ActionType]:
        """YAML → ActionType 객체 딕셔너리."""
        actions = {}
        for name, data in raw.get("actions", {}).items():
            preconditions = [
                Precondition(**p) for p in data.get("preconditions", [])
            ]
            effects = [
                Effect(**e) for e in data.get("effects", [])
            ]
            action = ActionType(
                name=name,
                actor_types=data.get("actor_types", []),
                target_types=data.get("target_types", []),
                preconditions=preconditions,
                effects=effects,
                cooldown=data.get("cooldown", 1),
                priority=data.get("priority", 5),
                description=data.get("description", ""),
            )
            actions[name] = action
        return actions

    def get_actions_for_type(self, object_type: str) -> list[ActionType]:
        """특정 Object Type이 수행 가능한 Action 목록을 우선순위 순으로 반환."""
        result = []
        for action in self._actions.values():
            if object_type in action.actor_types:
                result.append(action)
        return sorted(result, key=lambda a: -a.priority)

    def check_cooldown(
        self,
        entity_uid: str,
        action_name: str,
        current_round: int,
    ) -> bool:
        """쿨다운이 충족되었는지 확인한다."""
        action = self._actions.get(action_name)
        if not action:
            return False

        last_round = (
            self._cooldown_tracker
            .get(entity_uid, {})
            .get(action_name, -999)
        )
        return (current_round - last_round) >= action.cooldown

    def record_action(
        self,
        entity_uid: str,
        action_name: str,
        current_round: int,
    ) -> None:
        """Action 실행을 기록하여 쿨다운을 추적한다."""
        self._cooldown_tracker.setdefault(entity_uid, {})[action_name] = current_round

    def evaluate_preconditions(
        self,
        action: ActionType,
        entity: dict[str, Any],
        target: dict[str, Any] | None = None,
        graph_query_fn: Any = None,
    ) -> tuple[bool, list[dict[str, Any]]]:
        """
        Action의 전제조건을 평가한다.
        Returns: (all_met, [{"condition": ..., "met": bool, "margin": float}])
        """
        results = []
        for pre in action.preconditions:
            met, margin = self._evaluate_single(pre, entity, target, graph_query_fn)
            results.append({
                "type": pre.type,
                "property": pre.property or pre.comparison,
                "met": met,
                "margin": margin,
            })

        all_met = all(r["met"] for r in results)
        return all_met, results

    def _evaluate_single(
        self,
        pre: Precondition,
        entity: dict[str, Any],
        target: dict[str, Any] | None,
        graph_query_fn: Any,
    ) -> tuple[bool, float]:
        """개별 전제조건을 평가한다. Returns (met, margin)."""
        if pre.type == "property":
            return self._eval_property(pre, entity, target)
        elif pre.type == "relationship":
            if graph_query_fn:
                return self._eval_relationship(pre, entity, target, graph_query_fn)
            return True, 0.0
        elif pre.type == "community":
            return self._eval_community(pre, entity, target)
        elif pre.type == "proximity":
            if graph_query_fn:
                return self._eval_proximity(pre, entity, target, graph_query_fn)
            return True, 0.0
        else:
            return True, 0.0

    def _eval_property(
        self,
        pre: Precondition,
        entity: dict[str, Any],
        target: dict[str, Any] | None,
    ) -> tuple[bool, float]:
        """속성 비교 전제조건."""
        # comparison 필드: "abs(self.stance - target.stance)" 형식
        if pre.comparison:
            val = self._resolve_comparison(pre.comparison, entity, target)
        else:
            obj = entity if pre.target == "self" else (target or entity)
            val = obj.get(pre.property)

        if val is None:
            return False, 0.0

        val = float(val)
        threshold = float(pre.value)
        margin = val - threshold

        if pre.operator == ">":
            return val > threshold, margin
        elif pre.operator == "<":
            return val < threshold, -margin
        elif pre.operator == ">=":
            return val >= threshold, margin
        elif pre.operator == "<=":
            return val <= threshold, -margin
        elif pre.operator == "==":
            return val == threshold, 0.0 if val == threshold else abs(margin)
        return False, 0.0

    def _resolve_comparison(
        self,
        expr: str,
        entity: dict[str, Any],
        target: dict[str, Any] | None,
    ) -> float | None:
        """비교 표현식을 해석한다."""
        target = target or {}
        if expr.startswith("abs("):
            inner = expr[4:-1]
            parts = inner.split(" - ")
            if len(parts) == 2:
                a = self._get_nested_value(parts[0].strip(), entity, target)
                b = self._get_nested_value(parts[1].strip(), entity, target)
                if a is not None and b is not None:
                    return abs(float(a) - float(b))
        return None

    def _get_nested_value(
        self,
        path: str,
        entity: dict[str, Any],
        target: dict[str, Any],
    ) -> Any:
        """self.prop / target.prop 형식의 경로를 해석한다."""
        if path.startswith("self."):
            return entity.get(path[5:])
        elif path.startswith("target."):
            return target.get(path[7:])
        return None

    def _eval_relationship(
        self,
        pre: Precondition,
        entity: dict[str, Any],
        target: dict[str, Any] | None,
        graph_query_fn: Any,
    ) -> tuple[bool, float]:
        """관계 존재 여부."""
        exists = pre.condition == "exists"
        target_uid = (target or {}).get("uid", "")
        result = graph_query_fn(pre.pattern, entity.get("uid", ""), target_uid)
        met = bool(result) == exists
        return met, 1.0 if met else 0.0

    def _eval_community(
        self,
        pre: Precondition,
        entity: dict[str, Any],
        target: dict[str, Any] | None,
    ) -> tuple[bool, float]:
        """커뮤니티 조건."""
        target = target or {}
        src_comm = entity.get("community_id", "")
        tgt_comm = target.get("community_id", "")
        if "==" in pre.condition:
            met = src_comm == tgt_comm and src_comm != ""
        else:
            met = src_comm != tgt_comm
        return met, 1.0 if met else 0.0

    def _eval_proximity(
        self,
        pre: Precondition,
        entity: dict[str, Any],
        target: dict[str, Any] | None,
        graph_query_fn: Any,
    ) -> tuple[bool, float]:
        """N-hop 거리 조건."""
        target_uid = (target or {}).get("uid", "")
        # graph_query_fn으로 최단 경로 길이를 조회
        distance = graph_query_fn(
            "shortest_path", entity.get("uid", ""), target_uid
        )
        if distance is None:
            return False, 0.0
        met = distance <= pre.max_hops
        return met, float(pre.max_hops - distance)
