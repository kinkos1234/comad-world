"""중복 제거 & 가중치 — alias 기반 엔티티 병합 + 엣지 가중치 계산

refac.md 5.3 구현:
  1. exact normalize
  2. alias dictionary
  3. object_type 제약 기반 병합
  4. conservative merge (과병합 방지)
  5. merge decision log 저장
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

from ontology.schema import DomainOntology, Entity, Relationship

logger = logging.getLogger("comadeye")

# 한국어/영어 공통 alias 패턴
_DEFAULT_ALIASES: dict[str, list[str]] = {
    "미국": ["미합중국", "US", "USA", "United States", "America"],
    "중국": ["중화인민공화국", "PRC", "China"],
    "삼성전자": ["삼성", "Samsung", "Samsung Electronics"],
    "SK하이닉스": ["SK", "SK Hynix", "하이닉스"],
    "TSMC": ["Taiwan Semiconductor", "대만반도체"],
}


class Deduplicator:
    """엔티티 중복 제거 및 관계 가중치 재계산.

    개선점 (refac.md 5.3):
    - alias 테이블 기반 병합
    - object_type 제약 (다른 카테고리는 병합 금지)
    - conservative merge (유사도 높아도 확실하지 않으면 보류)
    - merge decision log
    """

    def __init__(
        self,
        similarity_threshold: float = 0.85,
        custom_aliases: dict[str, list[str]] | None = None,
    ):
        self._threshold = similarity_threshold
        self._merge_log: list[dict] = []

        # alias → canonical name 매핑 구축
        self._alias_map: dict[str, str] = {}
        aliases = {**_DEFAULT_ALIASES, **(custom_aliases or {})}
        for canonical, alias_list in aliases.items():
            canon_norm = self._norm(canonical)
            self._alias_map[canon_norm] = canonical
            for alias in alias_list:
                self._alias_map[self._norm(alias)] = canonical

    def deduplicate(self, ontology: DomainOntology) -> DomainOntology:
        """중복 엔티티를 병합하고 관계 가중치를 재계산한다."""
        self._merge_log = []

        # 1. alias 기반 엔티티 병합
        alias_merge_map = self._find_alias_duplicates(ontology.entities)

        # 2. 이름 유사도 기반 엔티티 병합 (object_type 제약 적용)
        similarity_merge_map = self._find_similar_duplicates(
            ontology.entities, exclude=set(alias_merge_map.keys())
        )

        merge_map = {**alias_merge_map, **similarity_merge_map}

        if merge_map:
            logger.info(
                f"엔티티 병합: {len(merge_map)}건 "
                f"(alias: {len(alias_merge_map)}, "
                f"유사도: {len(similarity_merge_map)})"
            )
            ontology = self._merge_entities(ontology, merge_map)

        # 3. 중복 관계 병합 + 가중치 재계산
        ontology = self._merge_relationships(ontology)

        logger.info(
            f"중복 제거 완료: 엔티티 {len(ontology.entities)}개, "
            f"관계 {len(ontology.relationships)}개"
        )
        return ontology

    def _find_alias_duplicates(
        self, entities: dict[str, Entity]
    ) -> dict[str, str]:
        """alias 테이블 기반 중복 탐지."""
        merge_map: dict[str, str] = {}
        canonical_to_uid: dict[str, str] = {}

        for uid, entity in entities.items():
            norm_name = self._norm(entity.name)
            canonical = self._alias_map.get(norm_name)
            if canonical:
                canonical_norm = self._norm(canonical)
                if canonical_norm in canonical_to_uid:
                    existing_uid = canonical_to_uid[canonical_norm]
                    if uid != existing_uid:
                        merge_map[uid] = existing_uid
                        self._merge_log.append({
                            "type": "alias",
                            "merged": entity.name,
                            "into": entities[existing_uid].name,
                            "canonical": canonical,
                        })
                else:
                    canonical_to_uid[canonical_norm] = uid

        return merge_map

    def _find_similar_duplicates(
        self,
        entities: dict[str, Entity],
        exclude: set[str] | None = None,
    ) -> dict[str, str]:
        """이름 유사도 + object_type 제약 기반 중복 탐지."""
        merge_map: dict[str, str] = {}
        excluded = exclude or set()
        uids = [uid for uid in entities if uid not in excluded]

        for i, uid_a in enumerate(uids):
            if uid_a in merge_map:
                continue
            for uid_b in uids[i + 1:]:
                if uid_b in merge_map:
                    continue

                ent_a = entities[uid_a]
                ent_b = entities[uid_b]

                # object_type 제약: 다른 카테고리면 병합 금지
                cat_a = getattr(ent_a, "object_type", "")
                cat_b = getattr(ent_b, "object_type", "")
                if cat_a and cat_b and cat_a != cat_b:
                    continue

                if self._is_similar(ent_a.name, ent_b.name):
                    if len(ent_a.name) >= len(ent_b.name):
                        merge_map[uid_b] = uid_a
                        self._merge_log.append({
                            "type": "similarity",
                            "merged": ent_b.name,
                            "into": ent_a.name,
                            "similarity": self._calc_similarity(ent_a.name, ent_b.name),
                        })
                    else:
                        merge_map[uid_a] = uid_b
                        self._merge_log.append({
                            "type": "similarity",
                            "merged": ent_a.name,
                            "into": ent_b.name,
                            "similarity": self._calc_similarity(ent_a.name, ent_b.name),
                        })

        return merge_map

    def _is_similar(self, a: str, b: str) -> bool:
        """두 이름이 유사한지 판단한다."""
        a_norm = self._norm(a)
        b_norm = self._norm(b)

        if a_norm == b_norm:
            return True

        if a_norm in b_norm or b_norm in a_norm:
            if min(len(a_norm), len(b_norm)) / max(len(a_norm), len(b_norm), 1) > 0.7:
                return True

        if len(a_norm) > 0 and len(b_norm) > 0:
            return self._calc_similarity(a, b) >= self._threshold

        return False

    def _calc_similarity(self, a: str, b: str) -> float:
        """두 이름의 유사도를 계산한다."""
        a_norm = self._norm(a)
        b_norm = self._norm(b)
        if not a_norm or not b_norm:
            return 0.0
        max_len = max(len(a_norm), len(b_norm))
        dist = self._levenshtein(a_norm, b_norm)
        return 1 - (dist / max_len)

    @staticmethod
    def _norm(name: str) -> str:
        """이름 정규화: 소문자 + 공백/밑줄 제거."""
        return name.lower().replace(" ", "").replace("_", "").strip()

    @staticmethod
    def _levenshtein(s1: str, s2: str) -> int:
        if len(s1) < len(s2):
            return Deduplicator._levenshtein(s2, s1)
        if len(s2) == 0:
            return len(s1)
        prev_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            curr_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (c1 != c2)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row
        return prev_row[-1]

    def _merge_entities(
        self,
        ontology: DomainOntology,
        merge_map: dict[str, str],
    ) -> DomainOntology:
        """중복 엔티티를 병합한다."""
        for dup_uid in merge_map:
            if dup_uid in ontology.entities:
                canonical = ontology.entities[merge_map[dup_uid]]
                dup = ontology.entities[dup_uid]
                canonical.source_chunks.extend(dup.source_chunks)
                if dup.description and dup.description not in (canonical.description or ""):
                    canonical.description = (
                        f"{canonical.description}; {dup.description}"
                        if canonical.description
                        else dup.description
                    )
                del ontology.entities[dup_uid]

        new_rels = []
        for rel in ontology.relationships:
            source = merge_map.get(rel.source_uid, rel.source_uid)
            target = merge_map.get(rel.target_uid, rel.target_uid)
            if source == target:
                continue
            rel.source_uid = source
            rel.target_uid = target
            new_rels.append(rel)
        ontology.relationships = new_rels

        return ontology

    def _merge_relationships(self, ontology: DomainOntology) -> DomainOntology:
        """동일 소스-타겟-타입 관계를 병합하고 가중치를 재계산한다."""
        grouped: dict[tuple[str, str, str], list[Relationship]] = defaultdict(list)
        for rel in ontology.relationships:
            key = (rel.source_uid, rel.target_uid, rel.link_type)
            grouped[key].append(rel)

        merged_rels = []
        for (src, tgt, lt), rels in grouped.items():
            if len(rels) == 1:
                merged_rels.append(rels[0])
            else:
                total_weight = sum(r.weight for r in rels)
                avg_confidence = sum(r.confidence for r in rels) / len(rels)
                merged = Relationship(
                    source_uid=src,
                    target_uid=tgt,
                    link_type=lt,
                    weight=total_weight,
                    confidence=avg_confidence,
                    source_chunk=rels[0].source_chunk,
                )
                merged_rels.append(merged)

        ontology.relationships = merged_rels
        return ontology

    def save_merge_log(self, output_path: str | Path) -> None:
        """merge decision log를 저장한다."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._merge_log, f, ensure_ascii=False, indent=2)
        if self._merge_log:
            logger.info(f"Merge log 저장: {len(self._merge_log)}건 → {path}")

    def save_deduped(
        self,
        ontology: DomainOntology,
        output_path: str | Path,
    ) -> None:
        """중복 제거된 트리플을 JSONL로 저장한다."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for rel in ontology.relationships:
                triple = {
                    "source": rel.source_uid,
                    "target": rel.target_uid,
                    "link_type": rel.link_type,
                    "weight": rel.weight,
                    "confidence": rel.confidence,
                }
                f.write(json.dumps(triple, ensure_ascii=False) + "\n")
