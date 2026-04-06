"""Tests for ingestion/extractor.py — comprehensive coverage.

Covers: EntityExtractor.extract(), _extract_chunks(), _extract_batch(),
_merge_results(), _normalize_names(), _normalize_rel_names(),
_merge_entities(), _extract_relationships_from_entities(),
_build_ontology(), _validate_and_fix_entity(),
_validate_and_fix_relationship(), _load_cache(), _save_cache(),
save_results(), _emit_progress().
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from ingestion.extractor import EntityExtractor
from ingestion.chunker import TextChunk
from ingestion.segmenter import Segment


# ───────────────────── Fixtures ─────────────────────


def _mock_llm(
    json_return: dict | list | None = None,
    text_return: str = "ok",
) -> MagicMock:
    """Create a mock LLMClient."""
    llm = MagicMock()
    if json_return is None:
        json_return = {
            "entities": [
                {
                    "name": "Alpha",
                    "object_type": "Actor",
                    "description": "Test entity",
                    "stance": 0.5,
                    "volatility": 0.3,
                    "influence_score": 0.8,
                },
                {
                    "name": "Beta",
                    "object_type": "Environment",
                    "description": "Another entity",
                    "stance": -0.2,
                    "volatility": 0.1,
                    "influence_score": 0.5,
                },
            ],
            "relationships": [
                {
                    "source": "Alpha",
                    "target": "Beta",
                    "link_type": "INFLUENCES",
                    "weight": 0.7,
                },
            ],
        }
    llm.generate_json.return_value = json_return
    llm.generate.return_value = text_return
    return llm


def _make_chunks(n: int = 3) -> list[TextChunk]:
    """Create n mock TextChunks."""
    return [
        TextChunk(
            chunk_id=f"chunk_{i}",
            text=f"Test text content for chunk {i}. Alpha and Beta are related.",
            token_count=20,
            offset=i * 100,
            chunk_index=i,
            source_file="test.txt",
        )
        for i in range(n)
    ]


def _make_segments(ref_offset: int = 200, ref_length: int = 100) -> list[Segment]:
    """Create segments with a reference segment."""
    return [
        Segment(
            segment_id="seg_0",
            segment_type="paragraph",
            title="Main",
            text="Main content",
            char_offset=0,
            char_length=200,
        ),
        Segment(
            segment_id="seg_1",
            segment_type="reference",
            title="References",
            text="Reference content",
            char_offset=ref_offset,
            char_length=ref_length,
        ),
    ]


# ───────────────────── Constructor ─────────────────────


class TestEntityExtractorInit:
    def test_default_init(self):
        extractor = EntityExtractor(llm=_mock_llm())
        assert extractor._concurrency == 1
        assert extractor._cache_dir is None

    def test_with_cache_dir(self, tmp_path):
        extractor = EntityExtractor(llm=_mock_llm(), cache_dir=tmp_path / "cache")
        assert extractor._cache_dir == tmp_path / "cache"

    def test_concurrency_minimum_one(self):
        extractor = EntityExtractor(llm=_mock_llm(), concurrency=0)
        assert extractor._concurrency == 1

    def test_progress_callback(self):
        callback = MagicMock()
        extractor = EntityExtractor(llm=_mock_llm(), on_progress=callback)
        assert extractor._on_progress is callback


# ───────────────────── Normalize Names ─────────────────────


class TestNormalizeNames:
    def test_strips_whitespace_and_quotes(self):
        entities = [{"name": '  "Test Name"  '}, {"name": "  'Another'  "}]
        result = EntityExtractor._normalize_names(entities)
        assert result[0]["name"] == "Test Name"
        assert result[1]["name"] == "Another"

    def test_collapses_multiple_spaces(self):
        entities = [{"name": "Entity   With   Spaces"}]
        result = EntityExtractor._normalize_names(entities)
        assert result[0]["name"] == "Entity With Spaces"

    def test_empty_name(self):
        entities = [{"name": ""}]
        result = EntityExtractor._normalize_names(entities)
        assert result[0]["name"] == ""


class TestNormalizeRelNames:
    def test_normalizes_source_and_target(self):
        rels = [{"source": '  "Alpha"  ', "target": "  Beta  "}]
        result = EntityExtractor._normalize_rel_names(rels)
        assert result[0]["source"] == "Alpha"
        assert result[0]["target"] == "Beta"


# ───────────────────── Merge Entities ─────────────────────


class TestMergeEntities:
    def test_merge_by_name(self):
        entities = [
            {"name": "Alpha", "description": "desc1", "stance": 0.5, "volatility": 0},
            {"name": "Alpha", "description": "desc2", "stance": 0, "volatility": 0.3},
        ]
        merged = EntityExtractor._merge_entities(entities)
        assert len(merged) == 1
        assert "desc1" in merged[0]["description"]
        assert "desc2" in merged[0]["description"]

    def test_no_merge_different_names(self):
        entities = [
            {"name": "Alpha", "description": "d1"},
            {"name": "Beta", "description": "d2"},
        ]
        merged = EntityExtractor._merge_entities(entities)
        assert len(merged) == 2

    def test_empty_name_skipped(self):
        entities = [
            {"name": "", "description": "d"},
            {"name": "Alpha", "description": "d"},
        ]
        merged = EntityExtractor._merge_entities(entities)
        assert len(merged) == 1
        assert merged[0]["name"] == "Alpha"

    def test_numeric_field_merge(self):
        entities = [
            {"name": "A", "stance": 0, "volatility": 0.5},
            {"name": "A", "stance": 0.3, "volatility": 0},
        ]
        merged = EntityExtractor._merge_entities(entities)
        assert merged[0]["stance"] == 0.3  # non-zero wins
        assert merged[0]["volatility"] == 0.5  # first non-zero kept

    def test_description_not_duplicated(self):
        entities = [
            {"name": "A", "description": "desc"},
            {"name": "A", "description": "desc"},
        ]
        merged = EntityExtractor._merge_entities(entities)
        assert merged[0]["description"] == "desc"  # not "desc; desc"

    def test_case_insensitive_key(self):
        entities = [
            {"name": "Alpha", "description": "d1"},
            {"name": "alpha", "description": "d2"},
        ]
        merged = EntityExtractor._merge_entities(entities)
        assert len(merged) == 1


# ───────────────────── Extract Batch ─────────────────────


class TestExtractBatch:
    def test_successful_batch(self):
        llm = _mock_llm()
        extractor = EntityExtractor(llm=llm)
        chunks = _make_chunks(1)
        result = extractor._extract_batch(0, chunks, 1)
        assert result is not None
        assert "entities" in result

    def test_batch_missing_entities_key(self):
        llm = _mock_llm(json_return={"other_key": "value"})
        extractor = EntityExtractor(llm=llm)
        chunks = _make_chunks(1)
        result = extractor._extract_batch(0, chunks, 1)
        assert result is None

    def test_batch_llm_exception(self):
        llm = MagicMock()
        llm.generate_json.side_effect = Exception("LLM failed")
        extractor = EntityExtractor(llm=llm)
        chunks = _make_chunks(1)
        result = extractor._extract_batch(0, chunks, 1)
        assert result is None

    def test_batch_list_response(self):
        llm = _mock_llm(json_return=[{"entities": [{"name": "A"}], "relationships": []}])
        extractor = EntityExtractor(llm=llm)
        chunks = _make_chunks(1)
        result = extractor._extract_batch(0, chunks, 1)
        assert result is not None
        assert "entities" in result

    def test_batch_empty_list_response(self):
        llm = _mock_llm(json_return=[])
        extractor = EntityExtractor(llm=llm)
        chunks = _make_chunks(1)
        result = extractor._extract_batch(0, chunks, 1)
        # Empty list -> {"entities": [], "relationships": []}
        assert result is not None

    def test_cache_hit(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        cached_data = {"entities": [{"name": "Cached"}], "relationships": []}
        (cache_dir / "batch_0.json").write_text(
            json.dumps(cached_data), encoding="utf-8"
        )

        llm = _mock_llm()
        extractor = EntityExtractor(llm=llm, cache_dir=cache_dir)
        chunks = _make_chunks(1)
        result = extractor._extract_batch(0, chunks, 1)
        assert result == cached_data
        # LLM should not be called on cache hit
        assert not llm.generate_json.called

    def test_cache_not_used_on_retry(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "batch_0.json").write_text('{"entities": []}', encoding="utf-8")

        llm = _mock_llm()
        extractor = EntityExtractor(llm=llm, cache_dir=cache_dir)
        chunks = _make_chunks(1)
        extractor._extract_batch(0, chunks, 1, retry_num=1)
        # On retry, cache is skipped and LLM is called
        assert llm.generate_json.called

    def test_cache_saved_after_extraction(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        llm = _mock_llm()
        extractor = EntityExtractor(llm=llm, cache_dir=cache_dir)
        chunks = _make_chunks(1)
        extractor._extract_batch(0, chunks, 1)
        assert (cache_dir / "batch_0.json").exists()

    def test_labeled_cache_key(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        llm = _mock_llm()
        extractor = EntityExtractor(llm=llm, cache_dir=cache_dir)
        chunks = _make_chunks(1)
        extractor._extract_batch(0, chunks, 1, label="main")
        assert (cache_dir / "batch_main_0.json").exists()


# ───────────────────── Extract Chunks ─────────────────────


class TestExtractChunks:
    def test_empty_chunks(self):
        extractor = EntityExtractor(llm=_mock_llm())
        result = extractor._extract_chunks([])
        assert result == []

    def test_sequential_extraction(self):
        llm = _mock_llm()
        extractor = EntityExtractor(llm=llm)
        chunks = _make_chunks(3)
        results = extractor._extract_chunks(chunks, label="test")
        assert len(results) == 3

    def test_failed_batch_retry(self):
        llm = MagicMock()
        # First call fails, retry succeeds
        llm.generate_json.side_effect = [
            Exception("fail"),
            {"entities": [{"name": "A"}], "relationships": []},
        ]
        extractor = EntityExtractor(llm=llm)
        chunks = _make_chunks(1)
        results = extractor._extract_chunks(chunks)
        assert len(results) == 1

    def test_all_retries_fail(self):
        llm = MagicMock()
        llm.generate_json.side_effect = Exception("always fail")
        extractor = EntityExtractor(llm=llm)
        chunks = _make_chunks(1)
        results = extractor._extract_chunks(chunks)
        assert len(results) == 0

    def test_progress_callback_called(self):
        callback = MagicMock()
        llm = _mock_llm()
        extractor = EntityExtractor(llm=llm, on_progress=callback)
        chunks = _make_chunks(2)
        extractor._extract_chunks(chunks)
        assert callback.called

    def test_concurrent_extraction(self):
        llm = _mock_llm()
        extractor = EntityExtractor(llm=llm, concurrency=2)
        chunks = _make_chunks(4)
        results = extractor._extract_chunks(chunks)
        assert len(results) == 4

    def test_concurrent_with_failures(self):
        call_count = 0

        def flaky_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("fail once")
            return {"entities": [{"name": "A"}], "relationships": []}

        llm = MagicMock()
        llm.generate_json.side_effect = flaky_generate
        extractor = EntityExtractor(llm=llm, concurrency=2)
        chunks = _make_chunks(2)
        results = extractor._extract_chunks(chunks)
        # At least one should succeed after retry
        assert len(results) >= 1


# ───────────────────── Full Extract ─────────────────────


class TestExtract:
    def test_basic_extract(self):
        llm = _mock_llm()
        extractor = EntityExtractor(llm=llm)
        chunks = _make_chunks(2)
        ontology = extractor.extract(chunks)
        assert len(ontology.entities) > 0
        assert len(ontology.relationships) >= 0

    def test_extract_with_segments(self):
        llm = _mock_llm()
        extractor = EntityExtractor(llm=llm)
        chunks = _make_chunks(3)
        segments = _make_segments(ref_offset=200, ref_length=100)
        ontology = extractor.extract(chunks, segments=segments)
        assert len(ontology.entities) > 0

    def test_extract_with_cache_dir(self, tmp_path):
        cache_dir = tmp_path / "cache"
        llm = _mock_llm()
        extractor = EntityExtractor(llm=llm, cache_dir=cache_dir)
        chunks = _make_chunks(1)
        extractor.extract(chunks)
        assert cache_dir.exists()

    def test_extract_triggers_relationship_supplement_when_empty(self):
        """When relationships are empty, supplementary extraction should be triggered."""
        llm = MagicMock()
        # First call returns entities but no relationships
        # Second call (supplement) returns relationships
        llm.generate_json.side_effect = [
            {
                "entities": [
                    {"name": "Alpha", "object_type": "Actor", "description": "d"},
                    {"name": "Beta", "object_type": "Actor", "description": "d"},
                ],
                "relationships": [],
            },
            {
                "relationships": [
                    {"source": "Alpha", "target": "Beta", "link_type": "INFLUENCES", "weight": 0.8},
                ],
            },
        ]
        extractor = EntityExtractor(llm=llm)
        chunks = _make_chunks(1)
        extractor.extract(chunks)
        # Should have called generate_json at least twice (original + supplement)
        assert llm.generate_json.call_count >= 2


# ───────────────────── Merge Results ─────────────────────


class TestMergeResults:
    def _make_extractor(self):
        return EntityExtractor(llm=_mock_llm())

    def test_merge_deduplicates_entities(self):
        extractor = self._make_extractor()
        chunk_results = [
            {"entities": [{"name": "Alpha", "object_type": "Actor", "description": "d1"}]},
            {"entities": [{"name": "Alpha", "object_type": "Actor", "description": "d2"}]},
        ]
        chunks = _make_chunks(2)
        ontology = extractor._merge_results(chunk_results, chunks)
        assert len(ontology.entities) == 1

    def test_merge_preserves_different_entities(self):
        extractor = self._make_extractor()
        chunk_results = [
            {"entities": [{"name": "Alpha", "object_type": "Actor", "description": "d"}]},
            {"entities": [{"name": "Beta", "object_type": "Actor", "description": "d"}]},
        ]
        chunks = _make_chunks(2)
        ontology = extractor._merge_results(chunk_results, chunks)
        assert len(ontology.entities) == 2

    def test_merge_validates_entities(self):
        extractor = self._make_extractor()
        chunk_results = [
            {
                "entities": [
                    {"name": "Good", "object_type": "Actor", "description": "d"},
                    {"name": "", "description": "should be dropped"},
                ],
            },
        ]
        chunks = _make_chunks(1)
        ontology = extractor._merge_results(chunk_results, chunks)
        assert "good" in ontology.entities  # uid is lowercased

    def test_merge_validates_relationships(self):
        extractor = self._make_extractor()
        chunk_results = [
            {
                "entities": [
                    {"name": "Alpha", "object_type": "Actor", "description": "d"},
                ],
                "relationships": [
                    {"source": "Alpha", "target": "NonExistent", "link_type": "INFLUENCES"},
                ],
            },
        ]
        chunks = _make_chunks(1)
        ontology = extractor._merge_results(chunk_results, chunks)
        # Relationship with nonexistent target should be dropped
        assert len(ontology.relationships) == 0


# ───────────────────── Build Ontology ─────────────────────


class TestBuildOntology:
    def _make_extractor(self):
        return EntityExtractor(llm=_mock_llm())

    def test_creates_entities_and_relationships(self):
        extractor = self._make_extractor()
        extraction = {
            "entities": [
                {"name": "Alpha", "object_type": "Actor", "description": "test"},
                {"name": "Beta", "object_type": "Environment", "description": "test"},
            ],
            "relationships": [
                {"source": "Alpha", "target": "Beta", "link_type": "INFLUENCES", "weight": 0.8},
            ],
            "object_types": [],
        }
        chunks = _make_chunks(1)
        ontology = extractor._build_ontology(extraction, chunks)
        assert "alpha" in ontology.entities
        assert "beta" in ontology.entities
        assert len(ontology.relationships) == 1

    def test_event_entities_get_special_properties(self):
        extractor = self._make_extractor()
        extraction = {
            "entities": [
                {
                    "name": "Crisis",
                    "object_type": "Event",
                    "category": "Event",
                    "description": "A crisis event",
                    "magnitude": 0.9,
                },
            ],
            "relationships": [],
            "object_types": [],
        }
        chunks = _make_chunks(1)
        ontology = extractor._build_ontology(extraction, chunks)
        entity = ontology.entities["crisis"]
        assert entity.properties["magnitude"] == 0.9
        assert entity.properties["is_active"] is False
        assert entity in ontology.initial_events

    def test_skips_relationship_with_missing_entities(self):
        extractor = self._make_extractor()
        extraction = {
            "entities": [{"name": "Alpha", "object_type": "Actor", "description": "d"}],
            "relationships": [
                {"source": "Alpha", "target": "Missing", "link_type": "INFLUENCES"},
            ],
            "object_types": [],
        }
        chunks = _make_chunks(1)
        ontology = extractor._build_ontology(extraction, chunks)
        assert len(ontology.relationships) == 0

    def test_custom_object_types(self):
        extractor = self._make_extractor()
        extraction = {
            "entities": [],
            "relationships": [],
            "object_types": [
                {"name": "CustomType", "parent": "Actor", "category": "Actor"},
            ],
        }
        chunks = _make_chunks(1)
        ontology = extractor._build_ontology(extraction, chunks)
        assert "CustomType" in ontology.object_types

    def test_empty_name_entity_skipped(self):
        extractor = self._make_extractor()
        extraction = {
            "entities": [{"name": "", "object_type": "Actor", "description": "d"}],
            "relationships": [],
            "object_types": [],
        }
        chunks = _make_chunks(1)
        ontology = extractor._build_ontology(extraction, chunks)
        assert len(ontology.entities) == 0

    def test_entity_uid_generation(self):
        extractor = self._make_extractor()
        extraction = {
            "entities": [{"name": "My Entity", "object_type": "Actor", "description": "d"}],
            "relationships": [],
            "object_types": [],
        }
        chunks = _make_chunks(1)
        ontology = extractor._build_ontology(extraction, chunks)
        assert "my_entity" in ontology.entities


# ───────────────────── Cache I/O ─────────────────────


class TestCacheIO:
    def test_load_cache_hit(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "test_key.json").write_text('{"key": "val"}', encoding="utf-8")

        extractor = EntityExtractor(llm=_mock_llm(), cache_dir=cache_dir)
        result = extractor._load_cache("test_key")
        assert result == {"key": "val"}

    def test_load_cache_miss(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        extractor = EntityExtractor(llm=_mock_llm(), cache_dir=cache_dir)
        result = extractor._load_cache("nonexistent")
        assert result is None

    def test_load_cache_no_cache_dir(self):
        extractor = EntityExtractor(llm=_mock_llm())
        result = extractor._load_cache("any_key")
        assert result is None

    def test_load_cache_corrupted_json(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "bad.json").write_text("not json{{", encoding="utf-8")

        extractor = EntityExtractor(llm=_mock_llm(), cache_dir=cache_dir)
        result = extractor._load_cache("bad")
        assert result is None

    def test_save_cache(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        extractor = EntityExtractor(llm=_mock_llm(), cache_dir=cache_dir)
        extractor._save_cache("mykey", {"data": True})
        assert (cache_dir / "mykey.json").exists()
        loaded = json.loads((cache_dir / "mykey.json").read_text(encoding="utf-8"))
        assert loaded == {"data": True}

    def test_save_cache_no_cache_dir(self):
        extractor = EntityExtractor(llm=_mock_llm())
        # Should not raise
        extractor._save_cache("key", {"data": True})


# ───────────────────── Save Results ─────────────────────


class TestSaveResults:
    def test_save_creates_files(self, tmp_path):
        llm = _mock_llm()
        extractor = EntityExtractor(llm=llm)
        chunks = _make_chunks(1)
        ontology = extractor.extract(chunks)

        output_dir = tmp_path / "output"
        extractor.save_results(ontology, output_dir)

        assert (output_dir / "ontology.json").exists()
        assert (output_dir / "triples.jsonl").exists()

    def test_triples_format(self, tmp_path):
        llm = _mock_llm()
        extractor = EntityExtractor(llm=llm)
        chunks = _make_chunks(1)
        ontology = extractor.extract(chunks)

        output_dir = tmp_path / "output"
        extractor.save_results(ontology, output_dir)

        lines = (output_dir / "triples.jsonl").read_text(encoding="utf-8").strip().split("\n")
        for line in lines:
            if line:
                triple = json.loads(line)
                assert "source" in triple
                assert "target" in triple
                assert "link_type" in triple


# ───────────────────── Emit Progress ─────────────────────


class TestEmitProgress:
    def test_callback_receives_correct_args(self):
        callback = MagicMock()
        extractor = EntityExtractor(llm=_mock_llm(), on_progress=callback)
        extractor._progress_completed = 3
        extractor._progress_total = 10
        extractor._progress_failed = 1
        extractor._progress_retrying = 0
        extractor._emit_progress("test message")

        callback.assert_called_once_with(3, 10, 1, 0, "test message")

    def test_no_callback(self):
        extractor = EntityExtractor(llm=_mock_llm())
        # Should not raise
        extractor._emit_progress("message")


# ───────────────────── Extract Relationships From Entities ─────────────────────


class TestExtractRelationshipsFromEntities:
    def test_successful_extraction(self):
        llm = MagicMock()
        llm.generate_json.return_value = {
            "relationships": [
                {"source": "A", "target": "B", "link_type": "INFLUENCES", "weight": 0.8},
            ],
        }
        extractor = EntityExtractor(llm=llm)
        chunks = _make_chunks(1)
        entities = [{"name": "A"}, {"name": "B"}]
        rels = extractor._extract_relationships_from_entities(chunks, entities)
        assert len(rels) == 1

    def test_llm_failure_continues(self):
        llm = MagicMock()
        llm.generate_json.side_effect = Exception("fail")
        extractor = EntityExtractor(llm=llm)
        chunks = _make_chunks(1)
        entities = [{"name": "A"}, {"name": "B"}]
        rels = extractor._extract_relationships_from_entities(chunks, entities)
        assert rels == []

    def test_empty_entities(self):
        llm = MagicMock()
        llm.generate_json.return_value = {"relationships": []}
        extractor = EntityExtractor(llm=llm)
        chunks = _make_chunks(1)
        rels = extractor._extract_relationships_from_entities(chunks, [])
        assert isinstance(rels, list)
