"""전파 엔진 — BFS 기반 영향 전파"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import Any

from graph.neo4j_client import Neo4jClient, _validate_property_name
from utils.config import load_yaml, project_root

logger = logging.getLogger("comadeye")


@dataclass
class PropagationEffect:
    """전파 효과."""
    source_uid: str
    target_uid: str
    effect: float
    distance: int
    rel_type: str
    property: str = "stance"


class PropagationEngine:
    """관계 경로를 따라 영향을 전파한다."""

    def __init__(
        self,
        client: Neo4jClient,
        decay: float = 0.6,
        max_hops: int = 3,
        min_threshold: float = 0.01,
    ):
        self._client = client
        self._decay = decay
        self._max_hops = max_hops
        self._threshold = min_threshold
        self._rules = self._load_rules()

    def _load_rules(self) -> dict[str, Any]:
        """전파 규칙을 로드한다."""
        try:
            raw = load_yaml(str(project_root() / "config" / "propagation_rules.yaml"))
            return raw.get("relationship_rules", {})
        except FileNotFoundError:
            return {}

    def propagate(
        self,
        impacted_nodes: list[tuple[str, float]],
    ) -> list[PropagationEffect]:
        """직접 영향 노드에서 BFS로 영향을 전파한다."""
        visited: set[str] = set()
        queue: deque[tuple[str, float, int]] = deque()
        effects: list[PropagationEffect] = []

        # 초기 영향 노드 삽입
        for uid, effect in impacted_nodes:
            queue.append((uid, effect, 0))
            visited.add(uid)

        while queue:
            uid, effect, distance = queue.popleft()

            if distance >= self._max_hops:
                continue

            # 이웃 노드 조회
            neighbors = self._client.get_neighbors(uid, active_only=True)

            for neighbor in neighbors:
                n_uid = neighbor["uid"]
                if n_uid in visited:
                    continue

                rel_type = neighbor.get("rel_type", "INFLUENCES")
                weight = float(neighbor.get("weight", 1.0))
                props = neighbor.get("props", {})
                susceptibility = float(props.get("susceptibility", 0.5))

                # 관계 유형별 전파 규칙 적용
                rule = self._rules.get(rel_type, {})
                inversion = rule.get("inversion", False)

                propagated = effect * self._decay * weight * susceptibility
                if inversion:
                    propagated = -propagated

                if abs(propagated) < self._threshold:
                    continue

                # 전파 속성 결정
                prop_properties = rule.get("propagated_properties", ["stance"])
                for prop in prop_properties:
                    effects.append(PropagationEffect(
                        source_uid=uid,
                        target_uid=n_uid,
                        effect=propagated,
                        distance=distance + 1,
                        rel_type=rel_type,
                        property=prop,
                    ))

                visited.add(n_uid)
                queue.append((n_uid, propagated, distance + 1))

        return effects

    def blast_radius(self, effects: list[PropagationEffect]) -> dict[str, Any]:
        """영향 범위(blast radius) 다차원 분석. GitNexus 차용 + 코마드 고유."""
        if not effects:
            return {"ratio": 0.0, "affected": 0, "by_distance": {}, "by_rel_type": {}}

        affected_uids = {e.target_uid for e in effects}
        total = self._client.query("MATCH (n:Entity) RETURN count(n) AS c")
        total_count = total[0]["c"] if total else 1

        by_distance: dict[int, int] = {}
        by_rel_type: dict[str, int] = {}
        for e in effects:
            by_distance[e.distance] = by_distance.get(e.distance, 0) + 1
            by_rel_type[e.rel_type] = by_rel_type.get(e.rel_type, 0) + 1

        return {
            "ratio": len(affected_uids) / max(total_count, 1),
            "affected": len(affected_uids),
            "total": total_count,
            "by_distance": by_distance,
            "by_rel_type": by_rel_type,
        }

    def apply_effects(
        self,
        effects: list[PropagationEffect],
    ) -> list[dict[str, Any]]:
        """전파 효과를 Neo4j에 배치로 적용한다."""
        if not effects:
            return []

        # 1. 대상 엔티티 일괄 조회
        target_uids = list({eff.target_uid for eff in effects})
        rows = self._client.query(
            "MATCH (n:Entity) WHERE n.uid IN $uids "
            "RETURN n.uid AS uid, properties(n) AS props",
            uids=target_uids,
        )
        entity_map = {r["uid"]: r["props"] for r in rows}

        # 2. 변경값 계산
        applied = []
        updates: list[dict[str, Any]] = []  # {uid, prop, new_val}

        for eff in effects:
            entity = entity_map.get(eff.target_uid)
            if not entity:
                continue

            old_val = float(entity.get(eff.property, 0.0))

            if eff.property == "stance":
                new_val = max(-1.0, min(1.0, old_val + eff.effect))
            elif eff.property == "volatility":
                new_val = max(0.0, min(1.0, old_val + abs(eff.effect)))
            else:
                new_val = old_val + eff.effect

            updates.append({
                "uid": eff.target_uid,
                "prop": eff.property,
                "val": new_val,
            })

            applied.append({
                "target": eff.target_uid,
                "property": eff.property,
                "old": old_val,
                "new": new_val,
                "delta": new_val - old_val,
                "source": eff.source_uid,
                "distance": eff.distance,
            })

        # 3. 일괄 쓰기 — 속성별로 그룹화하여 UNWIND
        props_seen: set[str] = {u["prop"] for u in updates}
        for prop in props_seen:
            safe_prop = _validate_property_name(prop)
            prop_updates = [
                {"uid": u["uid"], "val": u["val"]}
                for u in updates if u["prop"] == prop
            ]
            if prop_updates:
                self._client.write(
                    f"UNWIND $updates AS u "
                    f"MATCH (n:Entity {{uid: u.uid}}) "
                    f"SET n.{safe_prop} = u.val",
                    updates=prop_updates,
                )

        return applied
