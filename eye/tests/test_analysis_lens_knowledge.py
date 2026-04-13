"""Tests for analysis/lens_knowledge.py — LensPrinciple data + helper functions."""

from __future__ import annotations

from unittest.mock import MagicMock

from comad_eye.analysis.lens_knowledge import (
    LENS_PRINCIPLES,
    format_principles_for_prompt,
    load_lens_knowledge_to_graph,
    query_lens_principles,
)


# ── Data integrity ──


class TestLensPrinciples:
    def test_all_principles_have_required_fields(self):
        for p in LENS_PRINCIPLES:
            assert p.lens_id, f"Missing lens_id: {p.principle_id}"
            assert p.principle_id, f"Missing principle_id for {p.lens_id}"
            assert p.name, f"Missing name: {p.principle_id}"
            assert p.description, f"Missing description: {p.principle_id}"
            assert p.application_hint, f"Missing hint: {p.principle_id}"
            assert p.space_relevance, f"Missing relevance: {p.principle_id}"

    def test_unique_principle_ids(self):
        ids = [p.principle_id for p in LENS_PRINCIPLES]
        assert len(ids) == len(set(ids)), "Duplicate principle IDs"

    def test_unique_compound_keys(self):
        keys = [(p.lens_id, p.principle_id) for p in LENS_PRINCIPLES]
        assert len(keys) == len(set(keys)), "Duplicate (lens_id, principle_id) pairs"

    def test_valid_space_relevance(self):
        valid_spaces = {"hierarchy", "temporal", "recursive", "structural", "causal"}
        for p in LENS_PRINCIPLES:
            for space in p.space_relevance:
                assert space in valid_spaces, (
                    f"Invalid space '{space}' in {p.principle_id}"
                )

    def test_covers_all_10_lenses(self):
        lens_ids = set(p.lens_id for p in LENS_PRINCIPLES)
        expected = {
            "sun_tzu", "adam_smith", "taleb", "kahneman", "meadows",
            "descartes", "machiavelli", "clausewitz", "hegel", "darwin",
        }
        assert lens_ids == expected

    def test_each_lens_has_multiple_principles(self):
        from collections import Counter
        counts = Counter(p.lens_id for p in LENS_PRINCIPLES)
        for lens_id, count in counts.items():
            assert count >= 2, f"Lens {lens_id} has only {count} principles"


# ── load_lens_knowledge_to_graph ──


class TestLoadLensKnowledge:
    def test_writes_and_returns_count(self):
        client = MagicMock()
        count = load_lens_knowledge_to_graph(client)
        assert count == len(LENS_PRINCIPLES)
        # Should have called delete then create
        assert client.write.call_count == 2
        # First call: DELETE
        first_call = client.write.call_args_list[0]
        assert "DELETE" in first_call[0][0]

    def test_delete_before_create(self):
        client = MagicMock()
        load_lens_knowledge_to_graph(client)
        calls = client.write.call_args_list
        assert "DELETE" in calls[0][0][0]
        assert "CREATE" in calls[1][0][0]

    def test_principles_data_structure(self):
        """Verify that the data passed to write has expected keys."""
        client = MagicMock()
        load_lens_knowledge_to_graph(client)
        # Second call should have principles kwarg
        create_call = client.write.call_args_list[1]
        principles = create_call[1].get("principles", [])
        assert len(principles) == len(LENS_PRINCIPLES)
        for p in principles:
            assert "uid" in p
            assert "lens_id" in p
            assert "name" in p
            assert "description" in p
            assert "application_hint" in p
            assert "space_relevance" in p


# ── query_lens_principles ──


class TestQueryLensPrinciples:
    def test_query_with_space_name(self):
        client = MagicMock()
        client.query.return_value = [
            {"name": "세(勢)", "description": "Force", "application_hint": "hint1"},
        ]
        result = query_lens_principles(client, "sun_tzu", space_name="structural")
        assert len(result) == 1
        assert result[0]["name"] == "세(勢)"
        # Verify query included space filter
        query_str = client.query.call_args[0][0]
        assert "CONTAINS" in query_str

    def test_query_without_space_name(self):
        client = MagicMock()
        client.query.return_value = [
            {"name": "P1", "description": "D1", "application_hint": "H1"},
            {"name": "P2", "description": "D2", "application_hint": "H2"},
        ]
        result = query_lens_principles(client, "sun_tzu")
        assert len(result) == 2
        # Should not have space filter
        query_str = client.query.call_args[0][0]
        assert "CONTAINS" not in query_str

    def test_empty_results(self):
        client = MagicMock()
        client.query.return_value = []
        result = query_lens_principles(client, "sun_tzu", "hierarchy")
        assert result == []

    def test_missing_fields_default_empty(self):
        client = MagicMock()
        client.query.return_value = [{}]
        result = query_lens_principles(client, "sun_tzu")
        assert result == [{"name": "", "description": "", "application_hint": ""}]


# ── format_principles_for_prompt ──


class TestFormatPrinciplesForPrompt:
    def test_empty_list(self):
        assert format_principles_for_prompt([]) == ""

    def test_single_principle(self):
        result = format_principles_for_prompt([
            {"name": "Test Principle", "description": "A description", "application_hint": "Apply this way"},
        ])
        assert "Test Principle" in result
        assert "A description" in result
        assert "Apply this way" in result
        assert result.startswith("[")

    def test_multiple_principles_numbered(self):
        principles = [
            {"name": f"P{i}", "description": f"D{i}", "application_hint": f"H{i}"}
            for i in range(1, 4)
        ]
        result = format_principles_for_prompt(principles)
        assert "1. P1" in result
        assert "2. P2" in result
        assert "3. P3" in result

    def test_formatting_structure(self):
        result = format_principles_for_prompt([
            {"name": "Name", "description": "Desc", "application_hint": "Hint"},
        ])
        lines = result.strip().split("\n")
        assert lines[0] == "[참조 프레임워크 원리]"
        assert "1. Name" in lines[1]
