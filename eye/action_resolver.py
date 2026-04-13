"""Action 해결기 — 엔티티별 Action 전제조건 평가 및 실행"""

from __future__ import annotations

import logging
from typing import Any

from comad_eye.graph.neo4j_client import Neo4jClient
from comad_eye.ontology.action_registry import ActionRegistry

logger = logging.getLogger("comadeye")


class ActionResolver:
    """각 엔티티의 Action 전제조건을 평가하고 실행한다."""

    def __init__(
        self,
        client: Neo4jClient,
        registry: ActionRegistry,
        max_actions_per_entity: int = 1,
    ):
        self._client = client
        self._registry = registry
        self._max_actions = max_actions_per_entity

    def resolve(self, round_num: int) -> list[dict[str, Any]]:
        """모든 활성 엔티티의 Action을 해결한다."""
        action_log: list[dict[str, Any]] = []

        # 활성 엔티티 조회 (influence_score 내림차순)
        entities = self._client.query(
            "MATCH (n:Entity) WHERE n.activity_level > 0.1 "
            "RETURN properties(n) AS props "
            "ORDER BY n.influence_score DESC"
        )

        for record in entities:
            entity = record["props"]
            uid = entity.get("uid", "")
            obj_type = entity.get("object_type", "Actor")

            # 수행 가능한 Action 목록
            actions = self._registry.get_actions_for_type(obj_type)
            executed = 0

            for action in actions:
                if executed >= self._max_actions:
                    break

                # 쿨다운 체크
                if not self._registry.check_cooldown(
                    uid, action.name, round_num
                ):
                    continue

                # 전제조건 평가
                all_met, results = self._registry.evaluate_preconditions(
                    action=action,
                    entity=entity,
                    target=None,
                    graph_query_fn=self._graph_query,
                )

                if all_met:
                    # Action 실행
                    effects = self._apply_effects(action, entity, round_num)
                    self._registry.record_action(uid, action.name, round_num)

                    action_log.append({
                        "round": round_num,
                        "action": action.name,
                        "actor": uid,
                        "actor_name": entity.get("name", uid),
                        "preconditions": results,
                        "effects": effects,
                    })
                    executed += 1

        return action_log

    def _apply_effects(
        self,
        action: Any,
        entity: dict[str, Any],
        round_num: int,
    ) -> list[dict[str, Any]]:
        """Action 효과를 그래프에 적용한다."""
        effects_applied = []
        uid = entity.get("uid", "")

        for effect in action.effects:
            if effect.target == "self" or effect.target == "target":
                target_uid = uid
            else:
                target_uid = uid  # 기본은 self

            if effect.operation in ("add", "subtract", "multiply", "set"):
                self._apply_property_change(
                    target_uid, effect, entity, effects_applied
                )
            elif effect.operation == "create_edge":
                effects_applied.append({
                    "type": "create_edge",
                    "link_type": effect.link_type,
                    "source": uid,
                })
            elif effect.operation == "expire_edge":
                effects_applied.append({
                    "type": "expire_edge",
                    "relation": effect.relation,
                    "source": uid,
                    "round": round_num,
                })

        return effects_applied

    def _apply_property_change(
        self,
        target_uid: str,
        effect: Any,
        entity: dict[str, Any],
        effects_log: list[dict[str, Any]],
    ) -> None:
        """속성 변경 효과를 적용한다."""
        current = self._client.get_entity(target_uid)
        if not current:
            return

        prop = effect.property
        old_val = float(current.get(prop, 0.0))

        # value가 표현식인 경우 해석
        value = self._resolve_value(effect.value, entity)

        if effect.operation == "add":
            new_val = old_val + value
        elif effect.operation == "subtract":
            new_val = old_val - value
        elif effect.operation == "multiply":
            new_val = old_val * value
        elif effect.operation == "set":
            new_val = value
        else:
            return

        # 범위 제한
        if prop == "stance":
            new_val = max(-1.0, min(1.0, new_val))
        elif prop in ("volatility", "activity_level", "susceptibility"):
            new_val = max(0.0, min(1.0, new_val))

        self._client.update_entity_property(target_uid, prop, new_val)

        effects_log.append({
            "type": "property_change",
            "target": target_uid,
            "property": prop,
            "old": old_val,
            "new": new_val,
            "delta": new_val - old_val,
        })

    def _resolve_value(self, value: Any, entity: dict[str, Any]) -> float:
        """값 표현식을 해석한다."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # "self.influence_score * 0.3" 형식
            if "self." in value:
                parts = value.split("*")
                prop_expr = parts[0].strip().replace("self.", "")
                prop_val = float(entity.get(prop_expr, 0.5))
                if len(parts) > 1:
                    multiplier = float(parts[1].strip())
                    return prop_val * multiplier
                return prop_val
            try:
                return float(value)
            except ValueError:
                return 0.0
        return 0.0

    def _graph_query(
        self, pattern: str, source_uid: str, target_uid: str
    ) -> Any:
        """그래프 쿼리 콜백."""
        if pattern == "shortest_path":
            result = self._client.query(
                "MATCH p=shortestPath((a:Entity {uid: $src})-[*..5]-(b:Entity {uid: $tgt})) "
                "RETURN length(p) AS dist",
                src=source_uid,
                tgt=target_uid,
            )
            return result[0]["dist"] if result else None

        # 관계 존재 여부 확인
        rel_type = ""
        if ":" in pattern:
            rel_type = pattern.split(":")[1].split("]")[0].split("|")[0]

        if rel_type:
            result = self._client.query(
                f"MATCH (a:Entity {{uid: $src}})-[r:{rel_type}]->(b:Entity {{uid: $tgt}}) "
                f"RETURN count(r) AS cnt",
                src=source_uid,
                tgt=target_uid,
            )
        else:
            result = self._client.query(
                "MATCH (a:Entity {uid: $src})-[r]->(b:Entity {uid: $tgt}) "
                "RETURN count(r) AS cnt",
                src=source_uid,
                tgt=target_uid,
            )
        return result[0]["cnt"] > 0 if result else False
