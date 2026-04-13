"""Tests for ontology schema — data structures and operations."""

from __future__ import annotations

from comad_eye.ontology.schema import (
    DomainOntology,
    Entity,
    ObjectType,
    Relationship,
)


class TestEntity:
    def test_default_properties(self):
        e = Entity(uid="e1", name="Test", object_type="Actor")
        assert e.stance == 0.0
        assert e.volatility == 0.0
        assert e.influence_score == 0.5  # default influence score

    def test_set_stance(self):
        e = Entity(uid="e1", name="Test", object_type="Actor")
        e.stance = 0.75
        assert e.stance == 0.75
        assert e.properties["stance"] == 0.75

    def test_set_volatility(self):
        e = Entity(uid="e1", name="Test", object_type="Actor")
        e.volatility = 0.3
        assert e.volatility == 0.3

    def test_custom_properties(self):
        e = Entity(
            uid="e1", name="Test", object_type="Actor",
            properties={"custom_field": 42},
        )
        assert e.properties["custom_field"] == 42


class TestRelationship:
    def test_default_active(self):
        r = Relationship(source_uid="a", target_uid="b", link_type="INFLUENCES")
        assert r.is_active is True

    def test_expired(self):
        r = Relationship(source_uid="a", target_uid="b", link_type="INFLUENCES", expired_at=5)
        assert r.is_active is False

    def test_weight_default(self):
        r = Relationship(source_uid="a", target_uid="b", link_type="IMPACTS")
        assert r.weight == 1.0


class TestDomainOntology:
    def test_add_entity(self):
        onto = DomainOntology()
        e = Entity(uid="e1", name="Korea", object_type="Actor")
        onto.add_entity(e)
        assert "e1" in onto.entities
        assert onto.entities["e1"].name == "Korea"

    def test_add_event_entity(self):
        onto = DomainOntology()
        e = Entity(uid="ev1", name="Election", object_type="Event")
        onto.add_entity(e)
        assert e in onto.initial_events

    def test_add_relationship(self):
        onto = DomainOntology()
        r = Relationship(source_uid="a", target_uid="b", link_type="INFLUENCES")
        onto.add_relationship(r)
        assert len(onto.relationships) == 1

    def test_to_dict(self):
        onto = DomainOntology()
        onto.add_entity(Entity(uid="e1", name="Test", object_type="Actor"))
        onto.add_relationship(Relationship(
            source_uid="e1", target_uid="e2", link_type="IMPACTS",
        ))
        d = onto.to_dict()
        assert "entities" in d
        assert "relationships" in d

    def test_object_type_lookup(self):
        onto = DomainOntology()
        onto.object_types["Government"] = ObjectType(
            name="Government", category="Actor",
        )
        assert onto.object_types["Government"].category == "Actor"

    def test_get_actions_for_type(self):
        onto = DomainOntology()
        # No actions defined → empty list
        actions = onto.get_actions_for_type("Actor")
        assert actions == []
