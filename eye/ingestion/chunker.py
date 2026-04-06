"""텍스트 청킹 — kss 기반 한국어 문장 분리 + tiktoken 토큰 카운팅"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import kss
import tiktoken


@dataclass
class TextChunk:
    """텍스트 청크."""
    chunk_id: str
    text: str
    token_count: int
    offset: int  # 원문에서의 문자 오프셋
    chunk_index: int
    source_file: str = ""


class TextChunker:
    """시드데이터 텍스트를 청크로 분할한다."""

    def __init__(
        self,
        chunk_size: int = 600,
        chunk_overlap: int = 100,
        encoding_name: str = "cl100k_base",
    ):
        self._chunk_size = chunk_size
        self._overlap = chunk_overlap
        self._encoder = tiktoken.get_encoding(encoding_name)

    def chunk_file(self, file_path: str | Path) -> list[TextChunk]:
        """파일을 읽어 청크 리스트로 반환한다."""
        path = Path(file_path)
        text = path.read_text(encoding="utf-8")
        return self.chunk_text(text, source_file=path.name)

    def chunk_text(
        self,
        text: str,
        source_file: str = "",
    ) -> list[TextChunk]:
        """텍스트를 토큰 기준으로 청킹한다."""
        # kss로 문장 분리
        sentences = kss.split_sentences(text)

        chunks: list[TextChunk] = []
        current_sentences: list[str] = []
        current_tokens = 0
        current_offset = 0
        chunk_start_offset = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sent_tokens = len(self._encoder.encode(sentence))

            # 현재 청크에 추가할 수 있는지 확인
            if current_tokens + sent_tokens > self._chunk_size and current_sentences:
                # 현재 청크 저장
                chunk_text = " ".join(current_sentences)
                chunks.append(TextChunk(
                    chunk_id=f"chunk_{uuid.uuid4().hex[:8]}",
                    text=chunk_text,
                    token_count=current_tokens,
                    offset=chunk_start_offset,
                    chunk_index=len(chunks),
                    source_file=source_file,
                ))

                # 오버랩 적용: 마지막 N 토큰 분량의 문장 유지
                overlap_sentences: list[str] = []
                overlap_tokens = 0
                for s in reversed(current_sentences):
                    s_tok = len(self._encoder.encode(s))
                    if overlap_tokens + s_tok > self._overlap:
                        break
                    overlap_sentences.insert(0, s)
                    overlap_tokens += s_tok

                current_sentences = overlap_sentences
                current_tokens = overlap_tokens
                chunk_start_offset = current_offset - sum(
                    len(s) + 1 for s in overlap_sentences
                )

            current_sentences.append(sentence)
            current_tokens += sent_tokens
            current_offset += len(sentence) + 1

        # 마지막 청크
        if current_sentences:
            chunk_text = " ".join(current_sentences)
            chunks.append(TextChunk(
                chunk_id=f"chunk_{uuid.uuid4().hex[:8]}",
                text=chunk_text,
                token_count=current_tokens,
                offset=chunk_start_offset,
                chunk_index=len(chunks),
                source_file=source_file,
            ))

        return chunks

    def save_chunks(self, chunks: list[TextChunk], output_path: str | Path) -> None:
        """청크를 JSONL로 저장한다."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")

    @staticmethod
    def load_chunks(input_path: str | Path) -> list[TextChunk]:
        """JSONL에서 청크를 로드한다."""
        chunks = []
        with open(input_path, encoding="utf-8") as f:
            for line in f:
                data = json.loads(line.strip())
                chunks.append(TextChunk(**data))
        return chunks
