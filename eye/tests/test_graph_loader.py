"""Tests for graph/loader.py — ontology to Neo4j loading."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from comad_eye.graph.loader import GraphLoader, _get_parent_category, _SAFE_LABELS, _SAFE_REL_TYPES
from comad_eye.ontology.schema import (
    DomainOntology,
    Entity,
    ObjectType,
    Relationship,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    client = MagicMock()
    client.setup_schema = MagicMock()
    client.write = MagicMock()
    return client


@pytest.fixture
def loader(mock_client):
    return GraphLoader(mock_client)


def _make_ontology(
    entities=None,
    relationships=None,
    object_types=None,
) -> DomainOntology:
    onto = DomainOntology()
    if object_types:
        onto.object_types = object_types
    if entities:
        for e in entities:
            onto.add_entity(e)
    if relationships:
        for r in relationships:
            onto.add_relationship(r)
    return onto


# ---------------------------------------------------------------------------
# load() tests
# ---------------------------------------------------------------------------

class TestLoad:
    def test_calls_setup_schema(self, loader, mock_client):
        onto = _make_ontology()
        with patch.object(loader, "_load_lens_knowledge", return_value=0):
            loader.load(onto)
        mock_client.setup_schema.assert_called_once()

    def test_empty_ontology(self, loader, mock_client):
        onto = _make_ontology()
        with patch.object(loader, "_load_lens_knowledge", return_value=0):
            result = loader.load(onto)
        assert result["entities"] == 0
        assert result["relationships"] == 0
        assert result["lens_knowledge"] == 0

    def test_entities_loaded(self, loader, mock_client):
        onto = _make_ontology(
            entities=[
                Entity(uid="e1", name="Korea", object_type="Actor"),
                Entity(uid="e2", name="USA", object_type="Actor"),
            ],
            object_types={
                "Actor": ObjectType(name="Actor", category="Actor"),
            },
        )
        with patch.object(loader, "_load_lens_knowledge", return_value=0):
            result = loader.load(onto)
        assert result["entities"] == 2

    def test_relationships_loaded(self, loader, mock_client):
        onto = _make_ontology(
            entities=[
                Entity(uid="e1", name="A", object_type="Actor"),
                Entity(uid="e2", name="B", object_type="Actor"),
            ],
            relationships=[
                Relationship(source_uid="e1", target_uid="e2", link_type="INFLUENCES"),
            ],
            object_types={
                "Actor": ObjectType(name="Actor", category="Actor"),
            },
        )
        with patch.object(loader, "_load_lens_knowledge", return_value=0):
            result = loader.load(onto)
        assert result["relationships"] == 1


# ---------------------------------------------------------------------------
# _load_entities tests
# ---------------------------------------------------------------------------

class TestLoadEntities:
    def test_batch_write_called(self, loader, mock_client):
        onto = _make_ontology(
            entities=[Entity(uid="e1", name="Test", object_type="Actor")],
            object_types={"Actor": ObjectType(name="Actor", category="Actor")},
        )
        count = loader._load_entities(onto)
        assert count == 1
        # At least one write for batch UNWIND + one for label
        assert mock_client.write.call_count >= 1

    def test_unsafe_label_skipped(self, loader, mock_client):
        onto = _make_ontology(
            entities=[Entity(uid="e1", name="Test", object_type="Hacker")],
            object_types={
                "Hacker": ObjectType(name="Hacker", category="UnsafeCategory"),
            },
        )
        count = loader._load_entities(onto)
        assert count == 1
        # Write should be called for UNWIND but label SET should be skipped
        # (one write for batch, no write for unsafe label)

    def test_entity_properties_included(self, loader, mock_client):
        onto = _make_ontology(
            entities=[
                Entity(
                    uid="e1", name="Test", object_type="Actor",
                    properties={"stance": 0.5, "volatility": 0.3},
                    description="A test entity",
                )
            ],
        )
        count = loader._load_entities(onto)
        assert count == 1

    def test_empty_entities(self, loader, mock_client):
        onto = _make_ontology()
        count = loader._load_entities(onto)
        assert count == 0


# ---------------------------------------------------------------------------
# _load_relationships tests
# ---------------------------------------------------------------------------

class TestLoadRelationships:
    def test_safe_rel_type_loaded(self, loader, mock_client):
        onto = _make_ontology(
            relationships=[
                Relationship(source_uid="a", target_uid="b", link_type="INFLUENCES"),
            ],
        )
        count = loader._load_relationships(onto)
        assert count == 1

    def test_unsafe_rel_type_skipped(self, loader, mock_client):
        onto = _make_ontology(
            relationships=[
                Relationship(source_uid="a", target_uid="b", link_type="HACKS"),
            ],
        )
        count = loader._load_relationships(onto)
        assert count == 0

    def test_write_failure_continues(self, loader, mock_client):
        mock_client.write.side_effect = Exception("neo4j error")
        onto = _make_ontology(
            relationships=[
                Relationship(source_uid="a", target_uid="b", link_type="INFLUENCES"),
                Relationship(source_uid="c", target_uid="d", link_type="IMPACTS"),
            ],
        )
        count = loader._load_relationships(onto)
        assert count == 0  # both failed

    def test_all_safe_rel_types(self):
        expected = {"INFLUENCES", "IMPACTS", "BELONGS_TO", "COMPETES_WITH",
                    "DEPENDS_ON", "OPPOSES", "LEADS_TO"}
        assert _SAFE_REL_TYPES == expected


# ---------------------------------------------------------------------------
# _load_lens_knowledge tests
# ---------------------------------------------------------------------------

class TestLoadLensKnowledge:
    def test_success(self, loader):
        mock_fn = MagicMock(return_value=5)
        with patch.dict(
            "sys.modules",
            {"comad_eye.analysis.lens_knowledge": MagicMock(load_lens_knowledge_to_graph=mock_fn)},
        ):
            count = loader._load_lens_knowledge()
            assert count == 5
            mock_fn.assert_called_once()

    def test_failure_returns_zero(self, loader):
        with patch(
            "comad_eye.analysis.lens_knowledge.load_lens_knowledge_to_graph",
            side_effect=ImportError("not found"),
            create=True,
        ):
            count = loader._load_lens_knowledge()
            assert count == 0


# ---------------------------------------------------------------------------
# _get_parent_category tests
# ---------------------------------------------------------------------------

class TestGetParentCategory:
    def test_with_parent(self):
        onto = DomainOntology()
        onto.object_types["Government"] = ObjectType(
            name="Government", parent="Actor", category="Actor"
        )
        onto.object_types["Actor"] = ObjectType(name="Actor", category="Actor")
        result = _get_parent_category("Government", onto)
        assert result == "Actor"

    def test_no_parent(self):
        onto = DomainOntology()
        onto.object_types["Actor"] = ObjectType(name="Actor", category="Actor")
        result = _get_parent_category("Actor", onto)
        assert result == "Actor"  # falls back to "Actor"

    def test_unknown_type(self):
        onto = DomainOntology()
        result = _get_parent_category("Unknown", onto)
        assert result == "Actor"


# ---------------------------------------------------------------------------
# Constants tests
# ---------------------------------------------------------------------------

class TestConstants:
    def test_safe_labels(self):
        assert "Actor" in _SAFE_LABELS
        assert "Event" in _SAFE_LABELS
        assert "HACKER" not in _SAFE_LABELS

    def test_safe_rel_types(self):
        assert "INFLUENCES" in _SAFE_REL_TYPES
        assert "DELETE" not in _SAFE_REL_TYPES
