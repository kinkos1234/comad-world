"""세그멘터 — 문서를 의미 단위(세그먼트)로 분해

refac.md 4.2A: Segment Layer
제목/소제목, 단락, 표/리스트, 출처/부록 등 문맥 단위를 보존하여
이후 청킹 품질을 높인다.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger("comadeye")


@dataclass
class Segment:
    """의미 단위 세그먼트."""

    segment_id: str
    segment_type: str  # heading, paragraph, list, table, reference, appendix
    title: str  # 세그먼트 제목 (heading 텍스트 또는 자동 생성)
    text: str
    char_offset: int  # 원문에서의 문자 오프셋
    char_length: int
    depth: int = 0  # 헤딩 깊이 (# = 1, ## = 2, etc.)
    parent_id: str | None = None  # 상위 세그먼트
    metadata: dict = field(default_factory=dict)


# ── 정규식 패턴 ──

# 마크다운 헤딩: # ~ ######
_RE_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# 표: | 로 시작하는 연속 라인
_RE_TABLE_LINE = re.compile(r"^\|.+\|$")

# 리스트: -, *, 숫자. 으로 시작
_RE_LIST_ITEM = re.compile(r"^[\s]*[-*]|\d+[.)]\s")

# 참고/출처/부록 키워드
_RE_REFERENCE = re.compile(
    r"^(참고|출처|참조|reference|source|부록|appendix|bibliography)",
    re.IGNORECASE,
)

# 빈 줄
_RE_BLANK = re.compile(r"^\s*$")


class TextSegmenter:
    """문서를 의미 단위 세그먼트로 분해한다."""

    def __init__(self, min_segment_chars: int = 50):
        self._min_chars = min_segment_chars

    def segment(self, text: str) -> list[Segment]:
        """텍스트를 세그먼트 리스트로 분해한다."""
        lines = text.split("\n")
        segments: list[Segment] = []
        heading_stack: list[str] = []  # depth별 현재 heading segment_id

        i = 0
        offset = 0

        while i < len(lines):
            line = lines[i]

            # ── 헤딩 감지 ──
            heading_match = _RE_HEADING.match(line)
            if heading_match:
                depth = len(heading_match.group(1))
                title = heading_match.group(2).strip()

                # 참고/부록 감지
                seg_type = "heading"
                if _RE_REFERENCE.match(title):
                    seg_type = "reference"

                seg = Segment(
                    segment_id=_make_id(),
                    segment_type=seg_type,
                    title=title,
                    text=line,
                    char_offset=offset,
                    char_length=len(line),
                    depth=depth,
                    parent_id=self._find_parent(heading_stack, depth),
                )
                segments.append(seg)

                # heading stack 갱신
                while len(heading_stack) >= depth:
                    heading_stack.pop()
                heading_stack.append(seg.segment_id)

                offset += len(line) + 1
                i += 1
                continue

            # ── 표 감지 ──
            if _RE_TABLE_LINE.match(line.strip()):
                table_lines = []
                start_offset = offset
                while i < len(lines) and _RE_TABLE_LINE.match(lines[i].strip()):
                    table_lines.append(lines[i])
                    offset += len(lines[i]) + 1
                    i += 1

                table_text = "\n".join(table_lines)
                if len(table_text) >= self._min_chars:
                    segments.append(Segment(
                        segment_id=_make_id(),
                        segment_type="table",
                        title="(table)",
                        text=table_text,
                        char_offset=start_offset,
                        char_length=len(table_text),
                        parent_id=heading_stack[-1] if heading_stack else None,
                    ))
                continue

            # ── 리스트 감지 ──
            if _RE_LIST_ITEM.match(line):
                list_lines = []
                start_offset = offset
                while i < len(lines) and (
                    _RE_LIST_ITEM.match(lines[i])
                    or (lines[i].startswith("  ") and list_lines)
                ):
                    list_lines.append(lines[i])
                    offset += len(lines[i]) + 1
                    i += 1

                list_text = "\n".join(list_lines)
                if len(list_text) >= self._min_chars:
                    segments.append(Segment(
                        segment_id=_make_id(),
                        segment_type="list",
                        title="(list)",
                        text=list_text,
                        char_offset=start_offset,
                        char_length=len(list_text),
                        parent_id=heading_stack[-1] if heading_stack else None,
                    ))
                continue

            # ── 빈 줄 스킵 ──
            if _RE_BLANK.match(line):
                offset += len(line) + 1
                i += 1
                continue

            # ── 일반 단락 ──
            para_lines = []
            start_offset = offset
            while i < len(lines) and not _RE_BLANK.match(lines[i]):
                # 다음 헤딩, 표, 리스트가 나오면 중단
                if _RE_HEADING.match(lines[i]):
                    break
                if _RE_TABLE_LINE.match(lines[i].strip()):
                    break
                if _RE_LIST_ITEM.match(lines[i]) and not para_lines:
                    break
                para_lines.append(lines[i])
                offset += len(lines[i]) + 1
                i += 1

            if para_lines:
                para_text = "\n".join(para_lines)
                if len(para_text) >= self._min_chars:
                    # 참고/부록 단락 감지
                    seg_type = "paragraph"
                    if _RE_REFERENCE.match(para_text.strip()):
                        seg_type = "reference"

                    segments.append(Segment(
                        segment_id=_make_id(),
                        segment_type=seg_type,
                        title=self._extract_title(para_text),
                        text=para_text,
                        char_offset=start_offset,
                        char_length=len(para_text),
                        parent_id=heading_stack[-1] if heading_stack else None,
                    ))
                continue

            # fallback: 한 줄 전진
            offset += len(line) + 1
            i += 1

        # 너무 짧은 인접 세그먼트 병합
        segments = self._merge_small_segments(segments)

        logger.info(
            f"세그먼트 분해 완료: {len(segments)}개 "
            f"(heading={sum(1 for s in segments if s.segment_type == 'heading')}, "
            f"paragraph={sum(1 for s in segments if s.segment_type == 'paragraph')}, "
            f"table={sum(1 for s in segments if s.segment_type == 'table')}, "
            f"list={sum(1 for s in segments if s.segment_type == 'list')}, "
            f"reference={sum(1 for s in segments if s.segment_type == 'reference')})"
        )
        return segments

    def _merge_small_segments(self, segments: list[Segment]) -> list[Segment]:
        """최소 크기 미만인 인접 동일 유형 세그먼트를 병합한다."""
        if not segments:
            return segments

        merged: list[Segment] = [segments[0]]
        for seg in segments[1:]:
            prev = merged[-1]
            # 같은 타입 + 이전이 너무 짧으면 병합
            if (
                prev.segment_type == seg.segment_type
                and prev.segment_type in ("paragraph", "list")
                and prev.char_length < self._min_chars
            ):
                prev.text += "\n" + seg.text
                prev.char_length = len(prev.text)
            else:
                merged.append(seg)

        return merged

    @staticmethod
    def _find_parent(stack: list[str], depth: int) -> str | None:
        """현재 depth보다 상위인 가장 가까운 heading을 반환한다."""
        if depth <= 1 or not stack:
            return None
        idx = min(depth - 2, len(stack) - 1)
        return stack[idx] if idx >= 0 else None

    @staticmethod
    def _extract_title(text: str) -> str:
        """단락의 첫 문장을 제목으로 추출한다."""
        first_line = text.split("\n")[0].strip()
        if len(first_line) > 60:
            return first_line[:57] + "..."
        return first_line

    def save_segments(
        self, segments: list[Segment], output_path: str | Path
    ) -> None:
        """세그먼트를 JSONL로 저장한다."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for seg in segments:
                f.write(json.dumps(asdict(seg), ensure_ascii=False) + "\n")

    @staticmethod
    def load_segments(input_path: str | Path) -> list[Segment]:
        """JSONL에서 세그먼트를 로드한다."""
        segments = []
        with open(input_path, encoding="utf-8") as f:
            for line in f:
                data = json.loads(line.strip())
                segments.append(Segment(**data))
        return segments


def _make_id() -> str:
    return f"seg_{uuid.uuid4().hex[:8]}"
