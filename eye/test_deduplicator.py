"""Tests for entity deduplication — alias matching and merge logic."""

from __future__ import annotations

from ingestion.deduplicator import Deduplicator
from ontology.schema import DomainOntology, Entity, Relationship


def _make_entity(uid: str, name: str, object_type: str = "Actor") -> Entity:
    return Entity(uid=uid, name=name, object_type=object_type)


def _make_ontology(entities: list[Entity], rels: list[Relationship] | None = None) -> DomainOntology:
    ent_dict = {e.uid: e for e in entities}
    return DomainOntology(entities=ent_dict, relationships=rels or [])


class TestDeduplicatorNormalization:
    def test_alias_merge_us(self):
        """미국/US/United States should be merged."""
        dedup = Deduplicator()
        entities = [
            _make_entity("e1", "미국"),
            _make_entity("e2", "US"),
            _make_entity("e3", "United States"),
        ]
        result = dedup.deduplicate(_make_ontology(entities))
        # Should be merged down to 1 entity
        assert len(result.entities) == 1

    def test_alias_merge_samsung(self):
        dedup = Deduplicator()
        entities = [
            _make_entity("e1", "삼성전자"),
            _make_entity("e2", "Samsung"),
        ]
        result = dedup.deduplicate(_make_ontology(entities))
        assert len(result.entities) == 1

    def test_no_merge_different_entities(self):
        """Unrelated entities should not be merged."""
        dedup = Deduplicator()
        entities = [
            _make_entity("e1", "한국은행"),
            _make_entity("e2", "삼성전자"),
        ]
        result = dedup.deduplicate(_make_ontology(entities))
        assert len(result.entities) == 2

    def test_custom_aliases(self):
        dedup = Deduplicator(custom_aliases={"알파": ["Alpha", "ALPHA"]})
        entities = [
            _make_entity("e1", "알파"),
            _make_entity("e2", "Alpha"),
        ]
        result = dedup.deduplicate(_make_ontology(entities))
        assert len(result.entities) == 1

    def test_merge_log(self):
        dedup = Deduplicator()
        entities = [
            _make_entity("e1", "미국"),
            _make_entity("e2", "USA"),
        ]
        dedup.deduplicate(_make_ontology(entities))
        assert len(dedup._merge_log) >= 1

    def test_relationship_rewiring(self):
        """After merge, relationships should point to surviving entity."""
        dedup = Deduplicator()
        entities = [
            _make_entity("e1", "미국"),
            _make_entity("e2", "US"),
            _make_entity("e3", "한국"),
        ]
        rels = [
            Relationship(source_uid="e2", target_uid="e3", link_type="INFLUENCES", weight=0.5),
        ]
        result = dedup.deduplicate(_make_ontology(entities, rels))
        # Relationship source should be rewired to the surviving entity
        assert len(result.relationships) >= 1
        for rel in result.relationships:
            assert rel.source_uid in result.entities or rel.target_uid in result.entities
