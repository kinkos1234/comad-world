"""Tests for graph/summarizer.py — LLM-based community summarization."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from graph.summarizer import CommunitySummarizer, SUMMARY_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    client = MagicMock()
    client.get_entity = MagicMock(return_value={
        "name": "TestEntity",
        "object_type": "Actor",
        "stance": 0.5,
        "influence_score": 0.8,
    })
    client.query = MagicMock(return_value=[])
    return client


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.generate_json = MagicMock(return_value={
        "community_id": "C0_0",
        "title": "Test Community",
        "summary": "A community of test entities.",
        "key_entities": ["TestEntity"],
        "dominant_stance": 0.5,
        "cohesion": 0.8,
    })
    return llm


@pytest.fixture
def summarizer(mock_client, mock_llm):
    return CommunitySummarizer(mock_client, mock_llm)


# ---------------------------------------------------------------------------
# summarize() tests
# ---------------------------------------------------------------------------

class TestSummarize:
    def test_empty_communities(self, summarizer):
        result = summarizer.summarize({}, tier="C0")
        assert result == []

    def test_missing_tier(self, summarizer):
        result = summarizer.summarize({"C1": {"a": "C1_0"}}, tier="C0")
        assert result == []

    def test_single_community(self, summarizer, mock_llm):
        communities = {"C0": {"a": "C0_0", "b": "C0_0"}}
        result = summarizer.summarize(communities, tier="C0")
        assert len(result) == 1
        assert result[0]["title"] == "Test Community"
        mock_llm.generate_json.assert_called_once()

    def test_multiple_communities(self, summarizer, mock_llm):
        communities = {
            "C0": {
                "a": "C0_0", "b": "C0_0",
                "c": "C0_1", "d": "C0_1",
            }
        }
        result = summarizer.summarize(communities, tier="C0")
        assert len(result) == 2
        assert mock_llm.generate_json.call_count == 2

    def test_llm_returns_summaries_key(self, summarizer, mock_llm):
        """When LLM returns {"summaries": [...]}, it should be flattened."""
        mock_llm.generate_json.return_value = {
            "summaries": [
                {"community_id": "C0_0", "title": "Summary A"},
                {"community_id": "C0_0", "title": "Summary B"},
            ]
        }
        communities = {"C0": {"a": "C0_0"}}
        result = summarizer.summarize(communities)
        assert len(result) == 2

    def test_llm_failure_fallback(self, summarizer, mock_llm):
        mock_llm.generate_json.side_effect = Exception("LLM error")
        communities = {"C0": {"a": "C0_0", "b": "C0_0"}}
        result = summarizer.summarize(communities)
        assert len(result) == 1
        assert "멤버 2개" in result[0]["summary"]
        assert result[0]["dominant_stance"] == 0.0

    def test_community_id_set_in_result(self, summarizer, mock_llm):
        mock_llm.generate_json.return_value = {
            "title": "No ID Community",
            "summary": "Test",
        }
        communities = {"C0": {"a": "C0_0"}}
        result = summarizer.summarize(communities)
        assert result[0]["community_id"] == "C0_0"

    def test_default_tier_is_c0(self, summarizer, mock_llm):
        communities = {"C0": {"a": "C0_0"}}
        summarizer.summarize(communities)
        mock_llm.generate_json.assert_called_once()


# ---------------------------------------------------------------------------
# _build_community_context
# ---------------------------------------------------------------------------

class TestBuildCommunityContext:
    def test_includes_member_info(self, summarizer, mock_client):
        context = summarizer._build_community_context("C0_0", ["a", "b"])
        assert "TestEntity" in context
        assert "C0_0" in context

    def test_limits_members(self, summarizer, mock_client):
        # Should query at most 10 entities
        uids = [f"e{i}" for i in range(20)]
        summarizer._build_community_context("C0_0", uids)
        assert mock_client.get_entity.call_count == 10

    def test_entity_not_found(self, summarizer, mock_client):
        mock_client.get_entity.return_value = None
        context = summarizer._build_community_context("C0_0", ["missing"])
        assert "C0_0" in context

    def test_includes_relations(self, summarizer, mock_client):
        mock_client.query.return_value = [
            {"src": "A", "rel": "INFLUENCES", "tgt": "B", "w": 0.9},
        ]
        context = summarizer._build_community_context("C0_0", ["a", "b"])
        assert "INFLUENCES" in context


# ---------------------------------------------------------------------------
# _get_community_relations
# ---------------------------------------------------------------------------

class TestGetCommunityRelations:
    def test_empty_members(self, summarizer):
        result = summarizer._get_community_relations([])
        assert result == []

    def test_relations_formatted(self, summarizer, mock_client):
        mock_client.query.return_value = [
            {"src": "A", "rel": "INFLUENCES", "tgt": "B", "w": 0.9},
            {"src": "C", "rel": "IMPACTS", "tgt": "D", "w": 0.5},
        ]
        result = summarizer._get_community_relations(["a", "b", "c", "d"])
        assert len(result) == 2
        assert "INFLUENCES" in result[0]
        assert "0.90" in result[0]


# ---------------------------------------------------------------------------
# save() tests
# ---------------------------------------------------------------------------

class TestSave:
    def test_save_creates_json(self, summarizer):
        summaries = [
            {"community_id": "C0_0", "title": "Test"},
            {"community_id": "C0_1", "title": "Test2"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summaries.json"
            summarizer.save(summaries, path)
            assert path.exists()
            with open(path) as f:
                loaded = json.load(f)
            assert len(loaded) == 2

    def test_save_mkdir_parents(self, summarizer):
        summaries = [{"community_id": "C0_0"}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deep" / "nested" / "summaries.json"
            summarizer.save(summaries, path)
            assert path.exists()

    def test_save_empty_list(self, summarizer):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.json"
            summarizer.save([], path)
            with open(path) as f:
                loaded = json.load(f)
            assert loaded == []


# ---------------------------------------------------------------------------
# SUMMARY_SYSTEM_PROMPT constant
# ---------------------------------------------------------------------------

class TestConstants:
    def test_system_prompt_exists(self):
        assert len(SUMMARY_SYSTEM_PROMPT) > 0
        assert "JSON" in SUMMARY_SYSTEM_PROMPT
