"""인터뷰 합성기 — 엔티티 속성 기반 인용문 생성"""

from __future__ import annotations

import logging
from typing import Any

from comad_eye.graph.neo4j_client import Neo4jClient

logger = logging.getLogger("comadeye")


class InterviewSynthesizer:
    """엔티티의 그래프 속성에 기반하여 인터뷰 인용문을 생성한다."""

    def __init__(self, client: Neo4jClient):
        self._client = client

    def build_interview_context(
        self,
        entity_uids: list[str],
        actions_log: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """인터뷰 후보 엔티티의 컨텍스트를 수집한다."""
        contexts: list[dict[str, Any]] = []

        for uid in entity_uids:
            entity = self._client.get_entity(uid)
            if not entity:
                continue

            # 주요 관계 조회
            relationships = self._client.get_neighbors(uid, active_only=True)

            # Action 이력
            entity_actions = []
            if actions_log:
                entity_actions = [
                    a for a in actions_log if a.get("actor") == uid
                ][:5]

            contexts.append({
                "uid": uid,
                "name": entity.get("name", uid),
                "object_type": entity.get("object_type", "Entity"),
                "stance": float(entity.get("stance", 0)),
                "volatility": float(entity.get("volatility", 0)),
                "influence_score": float(entity.get("influence_score", 0)),
                "community_id": entity.get("community_id"),
                "key_relationships": [
                    {
                        "target": r.get("name", r.get("uid", "")),
                        "relation": r.get("rel_type", ""),
                        "weight": float(r.get("weight", 1.0)),
                    }
                    for r in relationships[:5]
                ],
                "action_history": [
                    a.get("action", "") for a in entity_actions
                ],
                "tone": self._determine_tone(entity),
                "intensity": self._determine_intensity(entity),
            })

        return contexts

    def generate_interview_prompt(
        self, entity_context: dict[str, Any]
    ) -> str:
        """인터뷰 프롬프트 조각을 생성한다."""
        name = entity_context["name"]
        obj_type = entity_context["object_type"]
        stance = entity_context["stance"]
        tone = entity_context["tone"]
        intensity = entity_context["intensity"]

        relationships_str = ", ".join(
            f"{r['relation']}→{r['target']}"
            for r in entity_context.get("key_relationships", [])[:3]
        )
        actions_str = ", ".join(
            entity_context.get("action_history", [])[:3]
        )

        return (
            f"엔티티: {name} ({obj_type})\n"
            f"stance: {stance:.2f} (어조: {tone})\n"
            f"influence: {entity_context['influence_score']:.2f} (강도: {intensity})\n"
            f"주요 관계: {relationships_str or '없음'}\n"
            f"최근 행동: {actions_str or '없음'}\n"
            f"인용문 형식: > \"인용문\" — {name}, {obj_type}\n"
        )

    @staticmethod
    def _determine_tone(entity: dict[str, Any]) -> str:
        """stance 값에 기반한 어조를 결정한다."""
        stance = float(entity.get("stance", 0))
        if stance > 0.3:
            return "긍정적/낙관적"
        elif stance < -0.3:
            return "부정적/비관적"
        else:
            return "중립적/분석적"

    @staticmethod
    def _determine_intensity(entity: dict[str, Any]) -> str:
        """influence_score에 기반한 어조 강도를 결정한다."""
        influence = float(entity.get("influence_score", 0))
        if influence > 0.7:
            return "단정적/선언적"
        elif influence > 0.4:
            return "확신적/분석적"
        else:
            return "관찰적/조심스러운"

    def validate_quote(
        self, quote: str, entity_context: dict[str, Any]
    ) -> bool:
        """인용문이 엔티티 속성과 일관되는지 검증한다."""
        tone = entity_context.get("tone", "")

        positive_words = ["상승", "성장", "호재", "긍정", "기회", "강세"]
        negative_words = ["하락", "위험", "악재", "우려", "약세", "위기"]

        has_positive = any(w in quote for w in positive_words)
        has_negative = any(w in quote for w in negative_words)

        if tone == "긍정적/낙관적" and has_negative and not has_positive:
            return False
        if tone == "부정적/비관적" and has_positive and not has_negative:
            return False

        return True
