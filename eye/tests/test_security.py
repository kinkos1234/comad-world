"""Tests for security: Cypher injection prevention."""

from __future__ import annotations

import pytest

from comad_eye.graph.neo4j_client import _validate_property_name, _SAFE_PROPERTY_NAMES
from comad_eye.graph.loader import _SAFE_LABELS, _SAFE_REL_TYPES


class TestPropertyNameValidation:
    def test_safe_names_pass(self):
        for name in _SAFE_PROPERTY_NAMES:
            assert _validate_property_name(name) == name

    def test_unsafe_name_raises(self):
        with pytest.raises(ValueError, match="Unsafe property name"):
            _validate_property_name("DROP DATABASE")

    def test_injection_attempt_raises(self):
        with pytest.raises(ValueError):
            _validate_property_name("stance} SET n.admin = true //")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            _validate_property_name("")

    def test_sql_injection_raises(self):
        with pytest.raises(ValueError):
            _validate_property_name("'; DROP TABLE users; --")


class TestLabelAllowlist:
    def test_expected_labels(self):
        expected = {"Actor", "Artifact", "Event", "Environment", "Concept"}
        assert _SAFE_LABELS == expected

    def test_unsafe_label_not_in_set(self):
        assert "Admin" not in _SAFE_LABELS
        assert "DETACH DELETE" not in _SAFE_LABELS


class TestRelTypeAllowlist:
    def test_expected_rel_types(self):
        assert "INFLUENCES" in _SAFE_REL_TYPES
        assert "IMPACTS" in _SAFE_REL_TYPES

    def test_unsafe_rel_type_not_in_set(self):
        assert "DELETE" not in _SAFE_REL_TYPES
        assert "MATCH (n) DETACH DELETE n" not in _SAFE_REL_TYPES
