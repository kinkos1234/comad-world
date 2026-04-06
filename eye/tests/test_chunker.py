"""Tests for ingestion/chunker.py — text chunking with kss + tiktoken."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from ingestion.chunker import TextChunk, TextChunker


# ---------------------------------------------------------------------------
# TextChunk dataclass tests
# ---------------------------------------------------------------------------

class TestTextChunk:
    def test_creation(self):
        chunk = TextChunk(
            chunk_id="chunk_abc",
            text="Hello world",
            token_count=2,
            offset=0,
            chunk_index=0,
            source_file="test.txt",
        )
        assert chunk.chunk_id == "chunk_abc"
        assert chunk.text == "Hello world"
        assert chunk.token_count == 2
        assert chunk.source_file == "test.txt"

    def test_default_source_file(self):
        chunk = TextChunk(
            chunk_id="c1",
            text="test",
            token_count=1,
            offset=0,
            chunk_index=0,
        )
        assert chunk.source_file == ""


# ---------------------------------------------------------------------------
# TextChunker construction
# ---------------------------------------------------------------------------

class TestTextChunkerConstruction:
    def test_default_params(self):
        chunker = TextChunker()
        assert chunker._chunk_size == 600
        assert chunker._overlap == 100

    def test_custom_params(self):
        chunker = TextChunker(chunk_size=200, chunk_overlap=50)
        assert chunker._chunk_size == 200
        assert chunker._overlap == 50


# ---------------------------------------------------------------------------
# chunk_text() tests
# ---------------------------------------------------------------------------

class TestChunkText:
    def test_empty_text(self):
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk_text("")
        assert chunks == []

    def test_short_text_single_chunk(self):
        chunker = TextChunker(chunk_size=1000, chunk_overlap=100)
        text = "이것은 짧은 테스트 문장입니다. 한국어 청킹을 테스트합니다."
        chunks = chunker.chunk_text(text)
        assert len(chunks) >= 1
        assert all(isinstance(c, TextChunk) for c in chunks)

    def test_chunk_ids_unique(self):
        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        text = "첫 번째 문장입니다. 두 번째 문장입니다. 세 번째 문장입니다. 네 번째 문장입니다. 다섯 번째 문장입니다."
        chunks = chunker.chunk_text(text)
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))

    def test_chunk_indexes_sequential(self):
        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        text = "첫 번째 문장입니다. 두 번째 문장입니다. 세 번째 문장입니다. 네 번째 문장입니다. 다섯 번째 문장입니다."
        chunks = chunker.chunk_text(text)
        if chunks:
            indexes = [c.chunk_index for c in chunks]
            assert indexes == list(range(len(chunks)))

    def test_source_file_passed(self):
        chunker = TextChunker(chunk_size=1000, chunk_overlap=100)
        chunks = chunker.chunk_text("Test text.", source_file="input.txt")
        if chunks:
            assert all(c.source_file == "input.txt" for c in chunks)

    def test_token_count_positive(self):
        chunker = TextChunker(chunk_size=1000, chunk_overlap=100)
        chunks = chunker.chunk_text("이것은 테스트 문장입니다. 토큰 수가 양수여야 합니다.")
        for chunk in chunks:
            assert chunk.token_count > 0

    def test_large_text_multiple_chunks(self):
        chunker = TextChunker(chunk_size=20, chunk_overlap=5)
        # Generate enough text to create multiple chunks
        sentences = [f"이것은 테스트 문장 번호 {i}입니다." for i in range(50)]
        text = " ".join(sentences)
        chunks = chunker.chunk_text(text)
        assert len(chunks) > 1


# ---------------------------------------------------------------------------
# chunk_file() tests
# ---------------------------------------------------------------------------

class TestChunkFile:
    def test_chunk_file(self):
        chunker = TextChunker(chunk_size=1000, chunk_overlap=100)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("파일에서 읽은 텍스트입니다. 청킹 테스트를 수행합니다.")
            f.flush()
            chunks = chunker.chunk_file(f.name)
        assert len(chunks) >= 1
        assert chunks[0].source_file.endswith(".txt")


# ---------------------------------------------------------------------------
# save_chunks / load_chunks tests
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def test_save_and_load_roundtrip(self):
        chunker = TextChunker(chunk_size=1000, chunk_overlap=100)
        original = [
            TextChunk(
                chunk_id="chunk_001",
                text="Test chunk 1",
                token_count=3,
                offset=0,
                chunk_index=0,
                source_file="test.txt",
            ),
            TextChunk(
                chunk_id="chunk_002",
                text="Test chunk 2",
                token_count=3,
                offset=13,
                chunk_index=1,
                source_file="test.txt",
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chunks.jsonl"
            chunker.save_chunks(original, path)

            loaded = TextChunker.load_chunks(path)
            assert len(loaded) == 2
            assert loaded[0].chunk_id == "chunk_001"
            assert loaded[1].text == "Test chunk 2"

    def test_save_creates_parent_dirs(self):
        chunker = TextChunker()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deep" / "nested" / "chunks.jsonl"
            chunker.save_chunks([], path)
            assert path.exists()

    def test_save_empty_list(self):
        chunker = TextChunker()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.jsonl"
            chunker.save_chunks([], path)
            assert path.exists()
            assert path.read_text() == ""

    def test_save_jsonl_format(self):
        chunker = TextChunker()
        chunks = [
            TextChunk(
                chunk_id="c1", text="hello", token_count=1,
                offset=0, chunk_index=0,
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.jsonl"
            chunker.save_chunks(chunks, path)
            lines = path.read_text().strip().split("\n")
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["chunk_id"] == "c1"
            assert data["text"] == "hello"
