"""온톨로지 스키마 — Palantir 4요소 모델 (Object/Link/Action/Property Type)"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Object Type ──────────────────────────────────────────────

@dataclass
class ObjectType:
    """엔티티 유형 정의."""
    name: str
    parent: str | None = None
    category: str = "Actor"  # Actor | Artifact | Event | Environment | Concept
    required_properties: list[str] = field(default_factory=list)
    optional_properties: list[str] = field(default_factory=list)
    allowed_actions: list[str] = field(default_factory=list)
    description: str = ""


# ── Link Type ────────────────────────────────────────────────

@dataclass
class LinkType:
    """관계 유형 정의."""
    name: str
    source_types: list[str] = field(default_factory=list)
    target_types: list[str] = field(default_factory=list)
    directed: bool = True
    default_properties: dict[str, Any] = field(default_factory=dict)
    description: str = ""


# ── Action Type ──────────────────────────────────────────────

@dataclass
class Precondition:
    """Action 전제조건."""
    type: str  # property | relationship | community | proximity | temporal
    target: str = "self"
    property: str = ""
    operator: str = ">"
    value: Any = None
    pattern: str = ""
    condition: str = ""
    comparison: str = ""
    max_hops: int = 2


@dataclass
class Effect:
    """Action 효과."""
    target: str = "target"
    source: str = ""
    property: str = ""
    operation: str = "add"  # add | subtract | multiply | set | blend | create_edge | expire_edge
    value: Any = None
    link_type: str = ""
    relation: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    blend_factor: float = 0.0


@dataclass
class ActionType:
    """엔티티가 수행할 수 있는 행동 유형."""
    name: str
    actor_types: list[str] = field(default_factory=list)
    target_types: list[str] = field(default_factory=list)
    preconditions: list[Precondition] = field(default_factory=list)
    effects: list[Effect] = field(default_factory=list)
    cooldown: int = 1
    priority: float = 5.0
    description: str = ""


# ── Property Type ────────────────────────────────────────────

@dataclass
class PropertyType:
    """속성 유형 정의."""
    name: str
    data_type: str = "float"  # float | int | str | bool | list | dict
    range_min: float | None = None
    range_max: float | None = None
    default: Any = None
    description: str = ""


# ── Entity (인스턴스) ────────────────────────────────────────

@dataclass
class Entity:
    """온톨로지 엔티티 인스턴스."""
    uid: str
    name: str
    object_type: str
    properties: dict[str, Any] = field(default_factory=dict)
    source_chunks: list[str] = field(default_factory=list)
    description: str = ""

    # 시뮬레이션 속성 (기본값)
    @property
    def stance(self) -> float:
        return float(self.properties.get("stance", 0.0))

    @stance.setter
    def stance(self, val: float) -> None:
        self.properties["stance"] = max(-1.0, min(1.0, val))

    @property
    def volatility(self) -> float:
        return float(self.properties.get("volatility", 0.0))

    @volatility.setter
    def volatility(self, val: float) -> None:
        self.properties["volatility"] = max(0.0, min(1.0, val))

    @property
    def influence_score(self) -> float:
        return float(self.properties.get("influence_score", 0.5))

    @property
    def susceptibility(self) -> float:
        return float(self.properties.get("susceptibility", 0.5))

    @property
    def activity_level(self) -> float:
        return float(self.properties.get("activity_level", 0.5))

    @property
    def community_id(self) -> str:
        return str(self.properties.get("community_id", ""))


# ── Relationship (인스턴스) ──────────────────────────────────

@dataclass
class Relationship:
    """관계 인스턴스."""
    source_uid: str
    target_uid: str
    link_type: str
    weight: float = 1.0
    confidence: float = 1.0
    source_chunk: str = ""
    created_at: int = -1  # -1 = 초기 추출
    expired_at: int | None = None  # None = 활성
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.expired_at is None


# ── Domain Ontology (컨테이너) ───────────────────────────────

@dataclass
class DomainOntology:
    """도메인 온톨로지 전체 컨테이너."""
    object_types: dict[str, ObjectType] = field(default_factory=dict)
    link_types: dict[str, LinkType] = field(default_factory=dict)
    action_types: dict[str, ActionType] = field(default_factory=dict)
    property_types: dict[str, PropertyType] = field(default_factory=dict)
    entities: dict[str, Entity] = field(default_factory=dict)
    relationships: list[Relationship] = field(default_factory=list)
    initial_events: list[Entity] = field(default_factory=list)

    def add_entity(self, entity: Entity) -> None:
        self.entities[entity.uid] = entity
        if entity.object_type == "Event":
            self.initial_events.append(entity)

    def add_relationship(self, rel: Relationship) -> None:
        self.relationships.append(rel)

    def get_actions_for_type(self, object_type: str) -> list[ActionType]:
        """특정 Object Type이 수행 가능한 Action 목록을 반환한다."""
        result = []
        for action in self.action_types.values():
            if object_type in action.actor_types:
                result.append(action)
        return result

    def to_dict(self) -> dict[str, Any]:
        """JSON 직렬화 가능한 딕셔너리로 변환한다."""
        import dataclasses
        return {
            "object_types": {
                k: dataclasses.asdict(v) for k, v in self.object_types.items()
            },
            "link_types": {
                k: dataclasses.asdict(v) for k, v in self.link_types.items()
            },
            "entities": {
                k: dataclasses.asdict(v) for k, v in self.entities.items()
            },
            "relationships": [
                dataclasses.asdict(r) for r in self.relationships
            ],
        }

    def save(self, path: str | Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> DomainOntology:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        onto = cls()
        for name, obj_data in data.get("object_types", {}).items():
            onto.object_types[name] = ObjectType(**obj_data)
        for name, link_data in data.get("link_types", {}).items():
            onto.link_types[name] = LinkType(**link_data)
        for uid, ent_data in data.get("entities", {}).items():
            entity = Entity(**ent_data)
            onto.add_entity(entity)
        for rel_data in data.get("relationships", []):
            onto.add_relationship(Relationship(**rel_data))
        return onto


# ── 기본 유형 정의 ───────────────────────────────────────────

BASE_OBJECT_TYPES = {
    "Actor": ObjectType(
        name="Actor", category="Actor",
        required_properties=["stance", "volatility", "influence_score", "susceptibility"],
        description="의지를 가진 행위자",
    ),
    "Artifact": ObjectType(
        name="Artifact", category="Artifact",
        required_properties=["stance"],
        description="행위자가 생산한 산출물",
    ),
    "Event": ObjectType(
        name="Event", category="Event",
        required_properties=["magnitude", "is_active"],
        description="시간 축 위의 발생 사건",
    ),
    "Environment": ObjectType(
        name="Environment", category="Environment",
        required_properties=["stance", "volatility"],
        description="행위자를 둘러싼 맥락/시장",
    ),
    "Concept": ObjectType(
        name="Concept", category="Concept",
        required_properties=["stance"],
        description="추상적 개념/테마",
    ),
}

BASE_LINK_TYPES = {
    "INFLUENCES": LinkType(name="INFLUENCES", description="A가 B에 영향을 미침"),
    "IMPACTS": LinkType(name="IMPACTS", description="이벤트가 엔티티에 충격"),
    "BELONGS_TO": LinkType(name="BELONGS_TO", description="A가 B에 속함"),
    "CONTAINS": LinkType(name="CONTAINS", description="A가 B를 포함"),
    "COMPETES_WITH": LinkType(name="COMPETES_WITH", directed=False, description="경쟁"),
    "ALLIED_WITH": LinkType(name="ALLIED_WITH", directed=False, description="협력"),
    "DEPENDS_ON": LinkType(name="DEPENDS_ON", description="A가 B에 의존"),
    "REACTS_TO": LinkType(name="REACTS_TO", description="A가 이벤트에 반응"),
    "SUPPLIES": LinkType(name="SUPPLIES", description="A가 B에 공급"),
    "REGULATES": LinkType(name="REGULATES", description="A가 B를 규제"),
    "OPPOSES": LinkType(name="OPPOSES", description="A가 B에 반대"),
    "LEADS_TO": LinkType(name="LEADS_TO", description="이벤트 A가 이벤트 B를 유발"),
}
