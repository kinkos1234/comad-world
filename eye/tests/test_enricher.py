"""Tests for ingestion/enricher.py — 31% → target 100%"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

from comad_eye.ingestion.enricher import VectorEnricher


def _make_ontology(entities=None):
    ontology = MagicMock()
    if entities is None:
        entities = {}
    ontology.entities = entities
    return ontology


def _make_entity(uid, name, obj_type="Entity", desc="description"):
    e = MagicMock()
    e.uid = uid
    e.name = name
    e.object_type = obj_type
    e.description = desc
    return e


class TestEnrich:
    def test_empty_ontology(self):
        enricher = VectorEnricher(embedding_service=MagicMock())
        ontology = _make_ontology({})
        result = enricher.enrich(ontology)
        assert result["entity_uids"] == []
        assert result["texts"] == []
        assert result["embeddings"] is None

    def test_single_entity(self):
        svc = MagicMock()
        svc.encode.return_value = np.array([[0.1, 0.2, 0.3]])
        enricher = VectorEnricher(embedding_service=svc)

        ontology = _make_ontology({"e1": _make_entity("e1", "Alpha", "Tech", "a technology")})
        result = enricher.enrich(ontology)

        assert result["entity_uids"] == ["e1"]
        assert len(result["texts"]) == 1
        assert "Alpha" in result["texts"][0]
        assert "Tech" in result["texts"][0]
        assert result["embeddings"].shape == (1, 3)

    def test_multiple_entities(self):
        svc = MagicMock()
        svc.encode.return_value = np.array([[0.1, 0.2], [0.3, 0.4]])
        enricher = VectorEnricher(embedding_service=svc)

        ontology = _make_ontology({
            "e1": _make_entity("e1", "A"),
            "e2": _make_entity("e2", "B"),
        })
        result = enricher.enrich(ontology)
        assert len(result["entity_uids"]) == 2
        assert result["embeddings"].shape == (2, 2)

    def test_text_format(self):
        svc = MagicMock()
        svc.encode.return_value = np.array([[0.0]])
        enricher = VectorEnricher(embedding_service=svc)

        ontology = _make_ontology({"e1": _make_entity("e1", "React", "Technology", "UI library")})
        enricher.enrich(ontology)

        call_args = svc.encode.call_args[0][0]
        assert call_args[0] == "React (Technology): UI library"


class TestSaveIndex:
    def test_saves_embeddings_and_index(self, tmp_path):
        svc = MagicMock()
        enricher = VectorEnricher(embedding_service=svc)

        enrichment = {
            "entity_uids": ["e1", "e2"],
            "texts": ["text1", "text2"],
            "embeddings": np.array([[0.1, 0.2], [0.3, 0.4]]),
        }
        enricher.save_index(enrichment, tmp_path)

        assert (tmp_path / "embeddings.npy").exists()
        assert (tmp_path / "index.json").exists()

        import json
        with open(tmp_path / "index.json") as f:
            index = json.load(f)
        assert index["count"] == 2
        assert index["dimension"] == 2
        assert index["entity_uids"] == ["e1", "e2"]

    def test_no_embeddings(self, tmp_path):
        enricher = VectorEnricher(embedding_service=MagicMock())
        enrichment = {
            "entity_uids": [],
            "texts": [],
            "embeddings": None,
        }
        enricher.save_index(enrichment, tmp_path)

        assert not (tmp_path / "embeddings.npy").exists()
        import json
        with open(tmp_path / "index.json") as f:
            index = json.load(f)
        assert index["dimension"] == 0

    def test_creates_directory(self, tmp_path):
        enricher = VectorEnricher(embedding_service=MagicMock())
        out = tmp_path / "sub" / "dir"
        enricher.save_index({"entity_uids": [], "texts": [], "embeddings": None}, out)
        assert (out / "index.json").exists()


class TestSearchSimilar:
    def test_missing_files_returns_empty(self, tmp_path):
        enricher = VectorEnricher(embedding_service=MagicMock())
        result = enricher.search_similar("query", tmp_path)
        assert result == []

    def test_successful_search(self, tmp_path):
        # Set up index files
        import json
        index = {"entity_uids": ["e1", "e2"], "texts": ["text1", "text2"], "dimension": 2, "count": 2}
        with open(tmp_path / "index.json", "w") as f:
            json.dump(index, f)
        np.save(str(tmp_path / "embeddings.npy"), np.array([[0.1, 0.2], [0.3, 0.4]]))

        svc = MagicMock()
        svc.search.return_value = [(0, 0.95, "text1"), (1, 0.80, "text2")]
        enricher = VectorEnricher(embedding_service=svc)

        result = enricher.search_similar("query", tmp_path, top_k=2)
        assert len(result) == 2
        assert result[0] == ("e1", 0.95, "text1")
        assert result[1] == ("e2", 0.80, "text2")

    def test_top_k_passed_through(self, tmp_path):
        import json
        with open(tmp_path / "index.json", "w") as f:
            json.dump({"entity_uids": [], "texts": [], "dimension": 0, "count": 0}, f)
        np.save(str(tmp_path / "embeddings.npy"), np.array([]))

        svc = MagicMock()
        svc.search.return_value = []
        enricher = VectorEnricher(embedding_service=svc)

        enricher.search_similar("q", tmp_path, top_k=10)
        assert svc.search.call_args[1]["top_k"] == 10
