"""임베딩 — BGE-M3 로컬 임베딩 + 코사인 유사도"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from comad_eye.config import EmbeddingsSettings, load_settings

if TYPE_CHECKING:
    from numpy.typing import NDArray


class EmbeddingService:
    """sentence-transformers 기반 로컬 임베딩 서비스."""

    def __init__(self, settings: EmbeddingsSettings | None = None):
        self._settings = settings or load_settings().embeddings
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(
                self._settings.model,
                device=self._settings.device,
            )
        return self._model

    def encode(self, texts: list[str]) -> NDArray[np.float32]:
        """텍스트 리스트를 임베딩 벡터로 변환한다."""
        model = self._load_model()
        embeddings = model.encode(
            texts,
            batch_size=self._settings.batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return np.array(embeddings, dtype=np.float32)

    def encode_single(self, text: str) -> NDArray[np.float32]:
        """단일 텍스트를 임베딩 벡터로 변환한다."""
        return self.encode([text])[0]

    @staticmethod
    def cosine_similarity(
        a: NDArray[np.float32],
        b: NDArray[np.float32],
    ) -> float:
        """두 벡터의 코사인 유사도를 계산한다 (정규화 가정)."""
        return float(np.dot(a, b))

    @staticmethod
    def batch_cosine_similarity(
        query: NDArray[np.float32],
        corpus: NDArray[np.float32],
    ) -> NDArray[np.float32]:
        """쿼리 벡터와 코퍼스 행렬 간 코사인 유사도를 계산한다."""
        return np.dot(corpus, query)

    def search(
        self,
        query: str,
        corpus_texts: list[str],
        corpus_embeddings: NDArray[np.float32],
        top_k: int = 5,
    ) -> list[tuple[int, float, str]]:
        """쿼리에 가장 유사한 텍스트를 검색한다."""
        query_emb = self.encode_single(query)
        similarities = self.batch_cosine_similarity(query_emb, corpus_embeddings)
        top_indices = np.argsort(similarities)[::-1][:top_k]
        return [
            (int(idx), float(similarities[idx]), corpus_texts[idx])
            for idx in top_indices
        ]

    def save_embeddings(
        self,
        embeddings: NDArray[np.float32],
        path: str,
    ) -> None:
        """임베딩 배열을 .npy 파일로 저장한다."""
        np.save(path, embeddings)

    @staticmethod
    def load_embeddings(path: str) -> NDArray[np.float32]:
        """저장된 임베딩 배열을 로드한다."""
        return np.load(path)
