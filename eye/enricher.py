"""벡터 의미 풍부화 — 엔티티 임베딩 생성 + 벡터 인덱스 구축"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

from comad_eye.ontology.schema import DomainOntology
from comad_eye.embeddings import EmbeddingService

logger = logging.getLogger("comadeye")


class VectorEnricher:
    """엔티티 임베딩 생성 및 벡터 인덱스 구축."""

    def __init__(self, embedding_service: EmbeddingService | None = None):
        self._embeddings = embedding_service or EmbeddingService()

    def enrich(self, ontology: DomainOntology) -> dict[str, Any]:
        """온톨로지의 모든 엔티티에 대해 임베딩을 생성한다."""
        entities = list(ontology.entities.values())
        if not entities:
            return {"entity_uids": [], "texts": [], "embeddings": None}

        # 엔티티 텍스트 구성: 이름 + 유형 + 설명
        texts = []
        uids = []
        for entity in entities:
            text = (
                f"{entity.name} ({entity.object_type}): "
                f"{entity.description}"
            )
            texts.append(text)
            uids.append(entity.uid)

        logger.info(f"임베딩 생성 시작: {len(texts)}개 엔티티")
        embeddings = self._embeddings.encode(texts)
        logger.info(f"임베딩 생성 완료: shape={embeddings.shape}")

        return {
            "entity_uids": uids,
            "texts": texts,
            "embeddings": embeddings,
        }

    def save_index(
        self,
        enrichment: dict[str, Any],
        output_dir: str | Path,
    ) -> None:
        """임베딩과 인덱스를 저장한다."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 임베딩 벡터
        if enrichment["embeddings"] is not None:
            np.save(
                str(output_dir / "embeddings.npy"),
                enrichment["embeddings"],
            )

        # 인덱스 매핑
        index = {
            "entity_uids": enrichment["entity_uids"],
            "texts": enrichment["texts"],
            "dimension": (
                enrichment["embeddings"].shape[1]
                if enrichment["embeddings"] is not None
                else 0
            ),
            "count": len(enrichment["entity_uids"]),
        }
        with open(output_dir / "index.json", "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

    def search_similar(
        self,
        query: str,
        index_dir: str | Path,
        top_k: int = 5,
    ) -> list[tuple[str, float, str]]:
        """유사 엔티티를 검색한다."""
        index_dir = Path(index_dir)
        index_path = index_dir / "index.json"
        embeddings_path = index_dir / "embeddings.npy"

        if not index_path.exists() or not embeddings_path.exists():
            return []

        with open(index_path, encoding="utf-8") as f:
            index = json.load(f)

        embeddings = np.load(str(embeddings_path))

        results = self._embeddings.search(
            query=query,
            corpus_texts=index["texts"],
            corpus_embeddings=embeddings,
            top_k=top_k,
        )

        return [
            (index["entity_uids"][idx], score, text)
            for idx, score, text in results
        ]
