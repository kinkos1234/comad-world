"""그래프 로더 — 온톨로지 → Neo4j 적재"""

from __future__ import annotations

import logging
from typing import Any

from comad_eye.graph.neo4j_client import Neo4jClient
from comad_eye.ontology.schema import DomainOntology

logger = logging.getLogger("comadeye")

# Allowlist for Neo4j node labels (from ontology categories)
_SAFE_LABELS = frozenset({"Actor", "Artifact", "Event", "Environment", "Concept"})
# Allowlist for relationship types
_SAFE_REL_TYPES = frozenset({
    "INFLUENCES", "IMPACTS", "BELONGS_TO", "COMPETES_WITH",
    "DEPENDS_ON", "OPPOSES", "LEADS_TO",
})


class GraphLoader:
    """DomainOntology를 Neo4j에 적재한다."""

    def __init__(self, client: Neo4jClient):
        self._client = client

    def load(self, ontology: DomainOntology) -> dict[str, int]:
        """온톨로지 전체를 Neo4j에 적재한다."""
        self._client.setup_schema()

        # 1. 엔티티 적재 (배치)
        entities_loaded = self._load_entities(ontology)

        # 2. 관계 적재 (배치)
        rels_loaded = self._load_relationships(ontology)

        # 3. 렌즈 지식 적재 (RAG 기반 렌즈 분석용)
        lens_knowledge_loaded = self._load_lens_knowledge()

        logger.info(
            f"그래프 적재 완료: 엔티티 {entities_loaded}개, "
            f"관계 {rels_loaded}개, 렌즈 지식 {lens_knowledge_loaded}개"
        )
        return {
            "entities": entities_loaded,
            "relationships": rels_loaded,
            "lens_knowledge": lens_knowledge_loaded,
        }

    def _load_entities(self, ontology: DomainOntology) -> int:
        """엔티티를 배치로 Neo4j에 적재한다."""
        entities_data = []
        for entity in ontology.entities.values():
            props: dict[str, Any] = {
                "uid": entity.uid,
                "name": entity.name,
                "object_type": entity.object_type,
                "description": entity.description,
            }
            props.update(entity.properties)
            entities_data.append(props)

        if not entities_data:
            return 0

        # UNWIND 배치 적재
        self._client.write(
            """
            UNWIND $entities AS e
            MERGE (n:Entity {uid: e.uid})
            SET n += e
            """,
            entities=entities_data,
        )

        # Object Type별 추가 라벨
        for entity in ontology.entities.values():
            category = ontology.object_types.get(
                entity.object_type, ontology.object_types.get(
                    _get_parent_category(entity.object_type, ontology), None
                )
            )
            if category:
                label = category.category
                if label not in _SAFE_LABELS:
                    logger.warning("Skipping unsafe label: %s", label)
                    continue
                self._client.write(
                    f"MATCH (n:Entity {{uid: $uid}}) SET n:{label}",
                    uid=entity.uid,
                )

        return len(entities_data)

    def _load_relationships(self, ontology: DomainOntology) -> int:
        """관계를 Neo4j에 적재한다."""
        count = 0
        for rel in ontology.relationships:
            if rel.link_type not in _SAFE_REL_TYPES:
                logger.warning("Skipping unsafe relationship type: %s", rel.link_type)
                continue
            try:
                self._client.write(
                    f"""
                    MATCH (a:Entity {{uid: $source}})
                    MATCH (b:Entity {{uid: $target}})
                    MERGE (a)-[r:{rel.link_type}]->(b)
                    SET r.weight = $weight,
                        r.confidence = $confidence,
                        r.created_at = $created_at,
                        r.source_chunk = $source_chunk
                    """,
                    source=rel.source_uid,
                    target=rel.target_uid,
                    weight=rel.weight,
                    confidence=rel.confidence,
                    created_at=rel.created_at,
                    source_chunk=rel.source_chunk,
                )
                count += 1
            except Exception as e:
                logger.warning(
                    f"관계 적재 실패: {rel.source_uid}-[{rel.link_type}]->"
                    f"{rel.target_uid}: {e}"
                )
        return count

    def _load_lens_knowledge(self) -> int:
        """렌즈 지식을 그래프에 적재한다."""
        try:
            from analysis.lens_knowledge import load_lens_knowledge_to_graph
            return load_lens_knowledge_to_graph(self._client)
        except Exception as e:
            logger.warning("렌즈 지식 적재 실패 (비치명적): %s", e)
            return 0


def _get_parent_category(
    object_type: str, ontology: DomainOntology
) -> str:
    """하위 유형의 상위 카테고리를 찾는다."""
    ot = ontology.object_types.get(object_type)
    if ot and ot.parent:
        parent_ot = ontology.object_types.get(ot.parent)
        if parent_ot:
            return parent_ot.name
    return "Actor"
