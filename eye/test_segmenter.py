"""Tests for ingestion/segmenter.py — document segmentation."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ingestion.segmenter import Segment, TextSegmenter, _make_id


# ---------------------------------------------------------------------------
# Segment dataclass tests
# ---------------------------------------------------------------------------

class TestSegment:
    def test_creation(self):
        seg = Segment(
            segment_id="seg_001",
            segment_type="heading",
            title="Test",
            text="# Test",
            char_offset=0,
            char_length=6,
            depth=1,
        )
        assert seg.segment_id == "seg_001"
        assert seg.segment_type == "heading"
        assert seg.depth == 1

    def test_default_values(self):
        seg = Segment(
            segment_id="seg_002",
            segment_type="paragraph",
            title="Para",
            text="Some text",
            char_offset=0,
            char_length=9,
        )
        assert seg.depth == 0
        assert seg.parent_id is None
        assert seg.metadata == {}


# ---------------------------------------------------------------------------
# _make_id tests
# ---------------------------------------------------------------------------

class TestMakeId:
    def test_starts_with_seg(self):
        assert _make_id().startswith("seg_")

    def test_unique(self):
        ids = {_make_id() for _ in range(100)}
        assert len(ids) == 100


# ---------------------------------------------------------------------------
# TextSegmenter construction
# ---------------------------------------------------------------------------

class TestSegmenterConstruction:
    def test_default_min_chars(self):
        seg = TextSegmenter()
        assert seg._min_chars == 50

    def test_custom_min_chars(self):
        seg = TextSegmenter(min_segment_chars=10)
        assert seg._min_chars == 10


# ---------------------------------------------------------------------------
# segment() — heading detection
# ---------------------------------------------------------------------------

class TestHeadingSegmentation:
    def test_single_heading(self):
        text = "# Main Title\n\nSome body text that is long enough to be a paragraph segment on its own."
        segmenter = TextSegmenter(min_segment_chars=10)
        segments = segmenter.segment(text)
        heading_segs = [s for s in segments if s.segment_type == "heading"]
        assert len(heading_segs) >= 1
        assert heading_segs[0].depth == 1
        assert heading_segs[0].title == "Main Title"

    def test_multiple_heading_depths(self):
        text = "# Title\n\n## Subtitle\n\n### Sub-subtitle\n\nBody text that is long enough to be a paragraph on its own."
        segmenter = TextSegmenter(min_segment_chars=10)
        segments = segmenter.segment(text)
        headings = [s for s in segments if s.segment_type == "heading"]
        depths = [h.depth for h in headings]
        assert 1 in depths
        assert 2 in depths
        assert 3 in depths

    def test_heading_parent_tracking(self):
        text = "# Parent\n\n## Child\n\nSome body text that is long enough for segmentation."
        segmenter = TextSegmenter(min_segment_chars=10)
        segments = segmenter.segment(text)
        headings = [s for s in segments if s.segment_type == "heading"]
        parent = headings[0]
        child = headings[1]
        assert child.parent_id == parent.segment_id

    def test_reference_heading(self):
        text = "# 참고문헌\n\nSome reference text that is long enough for a paragraph."
        segmenter = TextSegmenter(min_segment_chars=10)
        segments = segmenter.segment(text)
        ref_segs = [s for s in segments if s.segment_type == "reference"]
        assert len(ref_segs) >= 1


# ---------------------------------------------------------------------------
# segment() — table detection
# ---------------------------------------------------------------------------

class TestTableSegmentation:
    def test_table_detection(self):
        table = (
            "| Column A | Column B |\n"
            "| -------- | -------- |\n"
            "| Value 1  | Value 2  |\n"
            "| Value 3  | Value 4  |"
        )
        segmenter = TextSegmenter(min_segment_chars=10)
        segments = segmenter.segment(table)
        table_segs = [s for s in segments if s.segment_type == "table"]
        assert len(table_segs) >= 1

    def test_table_below_min_chars(self):
        table = "| A | B |\n| 1 | 2 |"
        segmenter = TextSegmenter(min_segment_chars=100)
        segments = segmenter.segment(table)
        table_segs = [s for s in segments if s.segment_type == "table"]
        assert len(table_segs) == 0


# ---------------------------------------------------------------------------
# segment() — list detection
# ---------------------------------------------------------------------------

class TestListSegmentation:
    def test_bullet_list(self):
        text = "- First item in the list with enough characters for min chars\n- Second item in the list with enough characters for min chars\n- Third item"
        segmenter = TextSegmenter(min_segment_chars=10)
        segments = segmenter.segment(text)
        list_segs = [s for s in segments if s.segment_type == "list"]
        assert len(list_segs) >= 1

    def test_numbered_list(self):
        text = "1. First numbered item that is long enough\n2. Second numbered item that is long enough\n3. Third numbered item"
        segmenter = TextSegmenter(min_segment_chars=10)
        segments = segmenter.segment(text)
        list_segs = [s for s in segments if s.segment_type == "list"]
        assert len(list_segs) >= 1

    def test_list_below_min_chars(self):
        text = "- a\n- b"
        segmenter = TextSegmenter(min_segment_chars=100)
        segments = segmenter.segment(text)
        list_segs = [s for s in segments if s.segment_type == "list"]
        assert len(list_segs) == 0


# ---------------------------------------------------------------------------
# segment() — paragraph detection
# ---------------------------------------------------------------------------

class TestParagraphSegmentation:
    def test_paragraph(self):
        text = "This is a normal paragraph with enough text to pass the minimum character threshold for segmentation."
        segmenter = TextSegmenter(min_segment_chars=10)
        segments = segmenter.segment(text)
        para_segs = [s for s in segments if s.segment_type == "paragraph"]
        assert len(para_segs) >= 1

    def test_paragraph_below_min_chars(self):
        text = "Short."
        segmenter = TextSegmenter(min_segment_chars=100)
        segments = segmenter.segment(text)
        assert len(segments) == 0

    def test_reference_paragraph(self):
        text = "참고: 이 섹션은 참고 자료입니다. 매우 긴 참고 텍스트를 여기에 작성하여 최소 문자 수를 충족시킵니다."
        segmenter = TextSegmenter(min_segment_chars=10)
        segments = segmenter.segment(text)
        ref_segs = [s for s in segments if s.segment_type == "reference"]
        assert len(ref_segs) >= 1


# ---------------------------------------------------------------------------
# segment() — blank line handling
# ---------------------------------------------------------------------------

class TestBlankLines:
    def test_blank_lines_between_paragraphs(self):
        text = (
            "First paragraph text that is long enough for minimum character threshold.\n"
            "\n"
            "Second paragraph text that is also long enough for minimum character threshold."
        )
        segmenter = TextSegmenter(min_segment_chars=10)
        segments = segmenter.segment(text)
        para_segs = [s for s in segments if s.segment_type == "paragraph"]
        assert len(para_segs) >= 1

    def test_all_blank_lines(self):
        text = "\n\n\n\n"
        segmenter = TextSegmenter(min_segment_chars=10)
        segments = segmenter.segment(text)
        assert segments == []


# ---------------------------------------------------------------------------
# _merge_small_segments
# ---------------------------------------------------------------------------

class TestMergeSmallSegments:
    def test_merge_adjacent_same_type(self):
        segmenter = TextSegmenter(min_segment_chars=100)
        segments = [
            Segment(
                segment_id="s1", segment_type="paragraph",
                title="Short", text="Short A", char_offset=0, char_length=7,
            ),
            Segment(
                segment_id="s2", segment_type="paragraph",
                title="Short B", text="Short B", char_offset=8, char_length=7,
            ),
        ]
        merged = segmenter._merge_small_segments(segments)
        assert len(merged) == 1
        assert "Short A" in merged[0].text
        assert "Short B" in merged[0].text

    def test_no_merge_different_types(self):
        segmenter = TextSegmenter(min_segment_chars=100)
        segments = [
            Segment(
                segment_id="s1", segment_type="paragraph",
                title="Short", text="Short A", char_offset=0, char_length=7,
            ),
            Segment(
                segment_id="s2", segment_type="heading",
                title="Title", text="# Title", char_offset=8, char_length=7,
            ),
        ]
        merged = segmenter._merge_small_segments(segments)
        assert len(merged) == 2

    def test_no_merge_heading_type(self):
        segmenter = TextSegmenter(min_segment_chars=100)
        segments = [
            Segment(
                segment_id="s1", segment_type="heading",
                title="H1", text="# H1", char_offset=0, char_length=4,
            ),
            Segment(
                segment_id="s2", segment_type="heading",
                title="H2", text="# H2", char_offset=5, char_length=4,
            ),
        ]
        merged = segmenter._merge_small_segments(segments)
        # heading types don't merge (only paragraph and list)
        assert len(merged) == 2

    def test_empty_segments(self):
        segmenter = TextSegmenter()
        result = segmenter._merge_small_segments([])
        assert result == []


# ---------------------------------------------------------------------------
# _find_parent
# ---------------------------------------------------------------------------

class TestFindParent:
    def test_depth_1_no_parent(self):
        assert TextSegmenter._find_parent(["s1"], 1) is None

    def test_depth_2_with_parent(self):
        assert TextSegmenter._find_parent(["s1"], 2) == "s1"

    def test_depth_3_with_parents(self):
        assert TextSegmenter._find_parent(["s1", "s2"], 3) == "s2"

    def test_empty_stack(self):
        assert TextSegmenter._find_parent([], 2) is None

    def test_depth_0_no_parent(self):
        assert TextSegmenter._find_parent(["s1"], 0) is None


# ---------------------------------------------------------------------------
# _extract_title
# ---------------------------------------------------------------------------

class TestExtractTitle:
    def test_short_text(self):
        title = TextSegmenter._extract_title("Short title")
        assert title == "Short title"

    def test_long_text_truncated(self):
        long_text = "A" * 100
        title = TextSegmenter._extract_title(long_text)
        assert len(title) == 60
        assert title.endswith("...")

    def test_multiline_uses_first_line(self):
        text = "First line\nSecond line\nThird line"
        title = TextSegmenter._extract_title(text)
        assert title == "First line"


# ---------------------------------------------------------------------------
# save_segments / load_segments
# ---------------------------------------------------------------------------

class TestSaveLoadSegments:
    def test_save_and_load_roundtrip(self):
        segmenter = TextSegmenter()
        segments = [
            Segment(
                segment_id="seg_001", segment_type="heading",
                title="Test", text="# Test", char_offset=0, char_length=6,
                depth=1,
            ),
            Segment(
                segment_id="seg_002", segment_type="paragraph",
                title="Body", text="Some text body", char_offset=7, char_length=14,
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "segments.jsonl"
            segmenter.save_segments(segments, path)
            loaded = TextSegmenter.load_segments(path)

        assert len(loaded) == 2
        assert loaded[0].segment_id == "seg_001"
        assert loaded[0].segment_type == "heading"
        assert loaded[1].title == "Body"

    def test_save_creates_parent_dirs(self):
        segmenter = TextSegmenter()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deep" / "nested" / "segments.jsonl"
            segmenter.save_segments([], path)
            assert path.exists()

    def test_save_jsonl_format(self):
        segmenter = TextSegmenter()
        segments = [
            Segment(
                segment_id="s1", segment_type="heading",
                title="T", text="# T", char_offset=0, char_length=3,
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.jsonl"
            segmenter.save_segments(segments, path)
            lines = path.read_text().strip().split("\n")
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["segment_id"] == "s1"


# ---------------------------------------------------------------------------
# Integration: full document segmentation
# ---------------------------------------------------------------------------

class TestFullDocumentSegmentation:
    def test_mixed_content(self):
        text = (
            "# Introduction\n"
            "\n"
            "This is a paragraph that provides an introduction to the topic being discussed in this document.\n"
            "\n"
            "## Details Section\n"
            "\n"
            "- First important detail item in this list\n"
            "- Second important detail item in this list\n"
            "- Third important detail item in this list\n"
            "\n"
            "| Column A | Column B | Column C |\n"
            "| -------- | -------- | -------- |\n"
            "| Data 1   | Data 2   | Data 3   |\n"
            "| Data 4   | Data 5   | Data 6   |\n"
            "\n"
            "## 참고문헌\n"
            "\n"
            "참고: 이 문서의 모든 데이터는 가상이며 테스트 목적으로만 사용됩니다."
        )
        segmenter = TextSegmenter(min_segment_chars=10)
        segments = segmenter.segment(text)

        types = {s.segment_type for s in segments}
        assert "heading" in types
        assert "paragraph" in types or "reference" in types

    def test_empty_text(self):
        segmenter = TextSegmenter(min_segment_chars=10)
        segments = segmenter.segment("")
        assert segments == []
