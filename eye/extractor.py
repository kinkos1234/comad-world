"""엔티티/관계 추출 — 3계층 파이프라인 (Segment → Chunk → Merge)

refac.md 4.2 구현:
  A. Segment Layer — 의미 단위 세그먼트 분해 (segmenter.py)
  B. Chunk Extraction Layer — 청크별 로컬 엔티티/관계 추출
  C. Reduce / Merge Layer — 청크 결과 병합 → 전역 온톨로지
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

from comad_eye.ingestion.chunker import TextChunk
from comad_eye.ingestion.segmenter import Segment
from comad_eye.ontology.schema import (
    BASE_LINK_TYPES,
    BASE_OBJECT_TYPES,
    DomainOntology,
    Entity,
    ObjectType,
    Relationship,
)
from comad_eye.llm_client import LLMClient

logger = logging.getLogger("comadeye")

EXTRACT_SYSTEM_PROMPT = """\
텍스트에서 엔티티와 관계를 JSON으로 추출하라.

엔티티 카테고리: Actor(사람/조직), Artifact(물건/작품), Event(사건), Environment(환경/장소), Concept(개념/아이디어)
관계 타입: INFLUENCES, IMPACTS, BELONGS_TO, COMPETES_WITH, DEPENDS_ON, OPPOSES, LEADS_TO

stance: -1.0(부정적)~1.0(긍정적). volatility: 0.0(안정)~1.0(변동). influence_score: 0.0~1.0.
엔티티마다 description을 반드시 한 문장으로 작성하라.
source/target은 반드시 entities의 name과 정확히 일치해야 한다.
모든 엔티티 쌍의 관계를 빠짐없이 추출하라. 암묵적 관계도 포함하라.

예시:
입력: "삼성전자는 반도체 시장에서 TSMC와 경쟁하고 있다."
출력: {"entities":[{"name":"삼성전자","object_type":"Actor","description":"반도체 제조 기업","stance":0.3,"volatility":0.4,"influence_score":0.8},{"name":"TSMC","object_type":"Actor","description":"세계 최대 파운드리 기업","stance":0.3,"volatility":0.3,"influence_score":0.9},{"name":"반도체 시장","object_type":"Environment","description":"글로벌 반도체 산업 환경","stance":0.0,"volatility":0.5,"influence_score":0.7}],"relationships":[{"source":"삼성전자","target":"TSMC","link_type":"COMPETES_WITH","weight":0.8},{"source":"삼성전자","target":"반도체 시장","link_type":"BELONGS_TO","weight":1.0},{"source":"TSMC","target":"반도체 시장","link_type":"BELONGS_TO","weight":1.0}]}
"""


class EntityExtractor:
    """3계층 파이프라인으로 엔티티·관계·온톨로지를 추출한다.

    Layer A: Segmenter (외부, segmenter.py)
    Layer B: Chunk Extraction (이 클래스)
    Layer C: Reduce / Merge (이 클래스)
    """

    # Progress callback signature: (completed, total, failed, retrying, message)
    ProgressCallback = Callable[[int, int, int, int, str], None]

    def __init__(
        self,
        llm: LLMClient | None = None,
        cache_dir: str | Path | None = None,
        on_progress: ProgressCallback | None = None,
        concurrency: int = 1,
    ):
        self._llm = llm or LLMClient()
        self._cache_dir = Path(cache_dir) if cache_dir else None
        self._on_progress = on_progress
        self._concurrency = max(1, concurrency)
        self._progress_completed = 0
        self._progress_total = 0
        self._progress_failed = 0
        self._progress_retrying = 0

    # 한 번에 보낼 최대 청크 수 (로컬 LLM 부하 제한 — 1개가 가장 안전)
    _BATCH_SIZE = 1
    # 실패 배치 재시도 횟수
    _MAX_RETRIES = 2

    # ──────────────────── Layer B: Chunk Extraction ────────────────────

    def extract(
        self,
        chunks: list[TextChunk],
        segments: list[Segment] | None = None,
    ) -> DomainOntology:
        """청크를 소규모 배치로 나눠 추출한 뒤 병합한다.

        segments가 제공되면 참고/부록 세그먼트에 속하는 청크는
        우선순위를 낮추어 처리한다.
        """
        # 참고/부록 청크 분류
        ref_offsets: set[tuple[int, int]] = set()
        if segments:
            for seg in segments:
                if seg.segment_type == "reference":
                    ref_offsets.add((seg.char_offset, seg.char_offset + seg.char_length))

        # 메인 청크와 참고용 청크 분리
        main_chunks = []
        ref_chunks = []
        for c in chunks:
            is_ref = any(
                start <= c.offset < end for start, end in ref_offsets
            )
            if is_ref:
                ref_chunks.append(c)
            else:
                main_chunks.append(c)

        if ref_chunks:
            logger.info(
                f"참고/부록 청크 {len(ref_chunks)}개 분리 "
                f"(메인 {len(main_chunks)}개)"
            )

        # 캐시 디렉토리 준비
        if self._cache_dir:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

        # 메인 청크 추출
        chunk_results = self._extract_chunks(main_chunks, label="main")

        # 참고 청크도 추출 (실패해도 계속)
        if ref_chunks:
            ref_results = self._extract_chunks(ref_chunks, label="ref")
            chunk_results.extend(ref_results)

        # Layer C: Merge
        return self._merge_results(chunk_results, chunks)

    def _extract_chunks(
        self,
        chunks: list[TextChunk],
        label: str = "",
    ) -> list[dict[str, Any]]:
        """청크 배치를 추출한다 (concurrency > 1이면 병렬)."""
        if not chunks:
            return []

        batches = [
            chunks[i : i + self._BATCH_SIZE]
            for i in range(0, len(chunks), self._BATCH_SIZE)
        ]

        tag = f"[{label}] " if label else ""
        conc_label = f" (병렬 {self._concurrency})" if self._concurrency > 1 else ""
        logger.info(
            f"{tag}엔티티 추출 시작: 청크 {len(chunks)}개 → "
            f"{len(batches)}개 배치{conc_label}"
        )

        self._progress_total += len(batches)
        self._emit_progress(f"{tag}추출 시작: {len(batches)}개 배치")

        results: list[dict[str, Any]] = []
        failed_batches: list[tuple[int, list[TextChunk]]] = []

        if self._concurrency > 1:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=self._concurrency) as pool:
                future_map = {
                    pool.submit(
                        self._extract_batch, idx, batch, len(batches), label,
                    ): (idx, batch)
                    for idx, batch in enumerate(batches)
                }
                for future in as_completed(future_map):
                    idx, batch = future_map[future]
                    try:
                        result = future.result()
                    except Exception:
                        result = None
                    if result is None:
                        failed_batches.append((idx, batch))
                        self._progress_failed += 1
                        self._emit_progress(f"{tag}배치 {idx + 1}/{len(batches)} 실패")
                    else:
                        results.append(result)
                        self._progress_completed += 1
                        self._emit_progress(f"{tag}배치 {idx + 1}/{len(batches)} 완료")
        else:
            for batch_idx, batch in enumerate(batches):
                result = self._extract_batch(
                    batch_idx, batch, len(batches), label=label,
                )
                if result is None:
                    failed_batches.append((batch_idx, batch))
                    self._progress_failed += 1
                    self._emit_progress(f"{tag}배치 {batch_idx + 1}/{len(batches)} 실패")
                    continue
                results.append(result)
                self._progress_completed += 1
                self._emit_progress(f"{tag}배치 {batch_idx + 1}/{len(batches)} 완료")

        # 실패 배치 재시도
        if failed_batches:
            logger.info(
                f"{tag}실패 배치 {len(failed_batches)}개 재시도 "
                f"(최대 {self._MAX_RETRIES}회)"
            )
            self._progress_retrying = len(failed_batches)
            self._emit_progress(f"{tag}실패 배치 {len(failed_batches)}개 재시도 중")
            for retry in range(self._MAX_RETRIES):
                still_failed: list[tuple[int, list[TextChunk]]] = []
                for batch_idx, batch in failed_batches:
                    result = self._extract_batch(
                        batch_idx, batch, len(batches),
                        retry_num=retry + 1, label=label,
                    )
                    if result is None:
                        still_failed.append((batch_idx, batch))
                        continue
                    results.append(result)
                    self._progress_completed += 1
                    self._progress_failed -= 1
                    self._progress_retrying = len(still_failed)
                    self._emit_progress(f"{tag}재시도 성공: 배치 {batch_idx + 1}")
                failed_batches = still_failed
                if not failed_batches:
                    self._progress_retrying = 0
                    break

            if failed_batches:
                self._progress_retrying = 0
                logger.warning(
                    f"{tag}최종 실패 배치 {len(failed_batches)}개 — 건너뜀"
                )
                self._emit_progress(f"{tag}최종 실패 {len(failed_batches)}개 건너뜀")

        return results

    def _extract_batch(
        self,
        batch_idx: int,
        batch: list[TextChunk],
        total: int,
        retry_num: int = 0,
        label: str = "",
    ) -> dict[str, Any] | None:
        """단일 배치를 추출한다. 캐시 히트 시 즉시 반환."""
        cache_key = f"batch_{label}_{batch_idx}" if label else f"batch_{batch_idx}"

        # 캐시 확인 (재시도가 아닐 때만)
        if retry_num == 0 and self._cache_dir:
            cached = self._load_cache(cache_key)
            if cached is not None:
                logger.info(f"배치 {batch_idx + 1}/{total} 캐시 히트")
                return cached

        batch_text = "\n\n".join(c.text for c in batch)
        prompt = (
            f"다음 텍스트에서 엔티티와 관계를 추출하세요.\n\n"
            f"<text>\n{batch_text}\n</text>"
        )

        tag = f"[{label}] " if label else ""
        retry_tag = f" (재시도 {retry_num})" if retry_num else ""
        logger.info(
            f"{tag}배치 {batch_idx + 1}/{total} 추출 중"
            f" (청크 {batch[0].chunk_index}~{batch[-1].chunk_index})"
            f"{retry_tag}"
        )
        try:
            result = self._llm.generate_json(
                prompt=prompt,
                system=EXTRACT_SYSTEM_PROMPT,
                task_type="extraction",
            )
            # 리스트 응답 → dict 변환 (일부 모델이 [{entities:...}] 반환)
            if isinstance(result, list):
                if len(result) > 0 and isinstance(result[0], dict):
                    result = result[0]
                else:
                    result = {"entities": [], "relationships": []}
            # 스키마 검증: entities 키 필수
            if "entities" not in result:
                logger.warning(
                    f"{tag}배치 {batch_idx + 1} 스키마 불일치{retry_tag}: "
                    f"keys={list(result.keys())}"
                )
                return None
        except Exception as e:
            logger.error(f"{tag}배치 {batch_idx + 1} 추출 실패{retry_tag}: {e}")
            return None

        # 캐시 저장
        if self._cache_dir:
            self._save_cache(cache_key, result)

        return result

    def _emit_progress(self, message: str) -> None:
        """진행 콜백 호출."""
        if self._on_progress:
            self._on_progress(
                self._progress_completed,
                self._progress_total,
                self._progress_failed,
                self._progress_retrying,
                message,
            )

    # ──────────────────── Layer C: Reduce / Merge ────────────────────

    def _merge_results(
        self,
        chunk_results: list[dict[str, Any]],
        chunks: list[TextChunk],
    ) -> DomainOntology:
        """청크별 추출 결과를 전역 온톨로지로 병합한다.

        병합 절차:
        1. 이름 정규화
        2. 동일 엔티티 병합 (나중 것이 우선, description 합성)
        3. 관계 중복 통합
        4. cross-chunk relation completion (관계 0건 시 2차 추출)
        """
        all_entities: list[dict] = []
        all_relationships: list[dict] = []
        all_object_types: list[dict] = []

        for result in chunk_results:
            all_entities.extend(result.get("entities", []))
            all_relationships.extend(result.get("relationships", []))
            all_object_types.extend(result.get("object_types", []))

        # 이름 정규화
        all_entities = self._normalize_names(all_entities)
        all_relationships = self._normalize_rel_names(all_relationships)

        # 엔티티 병합 (이름 기준, description 합성)
        merged_entities = self._merge_entities(all_entities)

        # ── 검증 & 보정 ──────────────────────────────────────────────────
        # 엔티티 검증
        validated_entities: list[dict] = []
        ent_fixed = 0
        ent_dropped = 0
        for ent in merged_entities:
            fixed = self._validate_and_fix_entity(ent)
            if fixed is None:
                ent_dropped += 1
            else:
                # 보정 여부 판단: 원본과 다르면 fix 카운트
                if fixed != ent:
                    ent_fixed += 1
                validated_entities.append(fixed)
        logger.info(
            f"엔티티 검증: {len(merged_entities)}개 중 "
            f"{ent_fixed}개 보정, {ent_dropped}개 제거"
        )
        merged_entities = validated_entities

        # 관계 검증
        entity_names: set[str] = {e["name"] for e in merged_entities}
        validated_rels: list[dict] = []
        rel_fixed = 0
        rel_dropped = 0
        for rel in all_relationships:
            fixed = self._validate_and_fix_relationship(rel, entity_names)
            if fixed is None:
                rel_dropped += 1
            else:
                if fixed != rel:
                    rel_fixed += 1
                validated_rels.append(fixed)
        logger.info(
            f"관계 검증: {len(all_relationships)}개 중 "
            f"{rel_fixed}개 보정, {rel_dropped}개 제거"
        )
        all_relationships = validated_rels
        # ─────────────────────────────────────────────────────────────────

        # cross-chunk relation completion (강화)
        # 관계가 0건이거나 엔티티 대비 관계 비율이 낮으면 2차 보강 추출
        rel_ratio = len(all_relationships) / max(len(merged_entities), 1)
        if merged_entities and (not all_relationships or rel_ratio < 0.7):
            reason = "0건" if not all_relationships else f"비율 {rel_ratio:.2f} (< 0.7)"
            logger.info(
                f"관계 보강 추출 시작 — 현재 관계 {len(all_relationships)}건, "
                f"엔티티 {len(merged_entities)}개, 이유: {reason}"
            )
            supplementary = self._extract_relationships_from_entities(
                chunks, merged_entities
            )
            # 기존 관계와 보강 관계 병합 (중복 제거)
            existing_keys = {
                (r.get("source", "").lower(), r.get("target", "").lower(), r.get("link_type", ""))
                for r in all_relationships
            }
            added = 0
            for rel in supplementary:
                key = (rel.get("source", "").lower(), rel.get("target", "").lower(), rel.get("link_type", ""))
                if key not in existing_keys:
                    all_relationships.append(rel)
                    existing_keys.add(key)
                    added += 1
            logger.info(f"관계 보강 완료: +{added}건 (총 {len(all_relationships)}건)")

        merged = {
            "entities": merged_entities,
            "relationships": all_relationships,
            "object_types": all_object_types,
        }
        return self._build_ontology(merged, chunks)

    @staticmethod
    def _normalize_names(entities: list[dict]) -> list[dict]:
        """엔티티 이름을 정규화한다."""
        for ent in entities:
            name = ent.get("name", "")
            name = name.strip().strip('"').strip("'")
            name = " ".join(name.split())
            ent["name"] = name
        return entities

    @staticmethod
    def _normalize_rel_names(rels: list[dict]) -> list[dict]:
        """관계의 source/target 이름을 정규화한다."""
        for rel in rels:
            for key in ("source", "target"):
                name = rel.get(key, "")
                name = name.strip().strip('"').strip("'")
                name = " ".join(name.split())
                rel[key] = name
        return rels

    @staticmethod
    def _merge_entities(entities: list[dict]) -> list[dict]:
        """이름 기준 병합. description을 합성한다."""
        seen: dict[str, dict] = {}
        for ent in entities:
            name = ent.get("name", "")
            if not name:
                continue
            key = name.lower().replace(" ", "_")
            if key in seen:
                existing = seen[key]
                # description 합성
                old_desc = existing.get("description", "")
                new_desc = ent.get("description", "")
                if new_desc and new_desc not in old_desc:
                    existing["description"] = (
                        f"{old_desc}; {new_desc}" if old_desc else new_desc
                    )
                # 수치 업데이트 (0이 아닌 값 우선)
                for field in ("stance", "volatility", "influence_score", "susceptibility", "magnitude"):
                    new_val = float(ent.get(field, 0))
                    old_val = float(existing.get(field, 0))
                    if new_val != 0 and old_val == 0:
                        existing[field] = new_val
            else:
                seen[key] = ent
        return list(seen.values())

    def _extract_relationships_from_entities(
        self,
        chunks: list[TextChunk],
        entities: list[dict],
    ) -> list[dict]:
        """엔티티 목록 + 청크별로 관계를 추출한다."""
        entity_names = [e.get("name", "") for e in entities if e.get("name")]
        entity_list = ", ".join(entity_names)

        rel_system = (
            "텍스트에서 엔티티 간 관계를 JSON으로 추출하라. "
            "관계: INFLUENCES, IMPACTS, BELONGS_TO, CONTAINS, COMPETES_WITH, "
            "ALLIED_WITH, DEPENDS_ON, REACTS_TO, SUPPLIES, REGULATES, OPPOSES, LEADS_TO. "
            "텍스트에 없는 관계 금지. source/target은 엔티티 목록의 이름만 사용."
        )

        all_rels: list[dict] = []
        batches = [
            chunks[i : i + self._BATCH_SIZE]
            for i in range(0, len(chunks), self._BATCH_SIZE)
        ]

        for batch_idx, batch in enumerate(batches):
            batch_text = "\n\n".join(c.text for c in batch)
            prompt = (
                f"엔티티: {entity_list}\n\n"
                f"<text>\n{batch_text}\n</text>\n\n"
                f"위 엔티티들 사이의 관계를 추출하세요.\n"
                f'출력: {{"relationships":[{{"source":"이름","target":"이름",'
                f'"link_type":"유형","weight":1.0,"description":"설명"}}]}}'
            )

            logger.info(f"2차 관계 추출 배치 {batch_idx + 1}/{len(batches)}")
            try:
                result = self._llm.generate_json(
                    prompt=prompt,
                    system=rel_system,
                    task_type="extraction",
                )
                all_rels.extend(result.get("relationships", []))
            except Exception as e:
                logger.error(f"2차 관계 배치 {batch_idx + 1} 실패: {e}")

        logger.info(f"2차 관계 추출 완료: {len(all_rels)}개")
        return all_rels

    # ──────────────────── Ontology Builder ────────────────────

    def _build_ontology(
        self,
        extraction: dict[str, Any],
        chunks: list[TextChunk],
    ) -> DomainOntology:
        """추출 결과를 DomainOntology 객체로 변환한다."""
        ontology = DomainOntology()

        for name, ot in BASE_OBJECT_TYPES.items():
            ontology.object_types[name] = ot
        for name, lt in BASE_LINK_TYPES.items():
            ontology.link_types[name] = lt

        for ot_data in extraction.get("object_types", []):
            name = ot_data.get("name", "")
            if name and name not in ontology.object_types:
                ontology.object_types[name] = ObjectType(
                    name=name,
                    parent=ot_data.get("parent"),
                    category=ot_data.get("category", "Actor"),
                )

        chunk_ids = [c.chunk_id for c in chunks]
        for ent_data in extraction.get("entities", []):
            name = ent_data.get("name", "")
            if not name:
                continue

            uid = name.replace(" ", "_").lower()
            entity = Entity(
                uid=uid,
                name=name,
                object_type=ent_data.get("object_type", "Actor"),
                properties={
                    "stance": float(ent_data.get("stance", 0.0)),
                    "volatility": float(ent_data.get("volatility", 0.0)),
                    "influence_score": float(ent_data.get("influence_score", 0.5)),
                    "susceptibility": float(ent_data.get("susceptibility", 0.5)),
                    "activity_level": 0.5,
                    "description": ent_data.get("description", ""),
                },
                source_chunks=chunk_ids[:3],
                description=ent_data.get("description", ""),
            )

            if ent_data.get("category") == "Event":
                entity.properties["magnitude"] = float(
                    ent_data.get("magnitude", 0.5)
                )
                entity.properties["is_active"] = False

            ontology.add_entity(entity)

        for rel_data in extraction.get("relationships", []):
            source_name = rel_data.get("source", "")
            target_name = rel_data.get("target", "")
            source_uid = source_name.replace(" ", "_").lower()
            target_uid = target_name.replace(" ", "_").lower()

            if source_uid not in ontology.entities or target_uid not in ontology.entities:
                continue

            rel = Relationship(
                source_uid=source_uid,
                target_uid=target_uid,
                link_type=rel_data.get("link_type", "INFLUENCES"),
                weight=float(rel_data.get("weight", 1.0)),
                confidence=1.0,
            )
            ontology.add_relationship(rel)

        logger.info(
            f"추출 완료: 엔티티 {len(ontology.entities)}개, "
            f"관계 {len(ontology.relationships)}개, "
            f"이벤트 {len(ontology.initial_events)}개"
        )
        return ontology

    # ──────────────────── Validation Helpers ────────────────────

    # 허용 object_type 집합
    _VALID_OBJECT_TYPES: frozenset[str] = frozenset(
        {"Actor", "Artifact", "Event", "Environment", "Concept"}
    )

    # 허용 link_type 집합 (BASE_LINK_TYPES 키 + EXTRACT_SYSTEM_PROMPT에 나열된 것)
    _VALID_LINK_TYPES: frozenset[str] = frozenset(BASE_LINK_TYPES.keys())

    @staticmethod
    def _validate_and_fix_entity(entity: dict) -> dict | None:
        """엔티티 딕셔너리를 검증하고 보정한다.

        - name 없으면 None 반환 (드롭)
        - description 없으면 name으로 기본값
        - object_type 이 허용 목록 외이면 "Concept"으로 교정
        - stance / volatility / influence_score 범위 클램프
        각 보정마다 WARNING 로그를 남긴다.
        """
        fixes: list[str] = []

        # 1. name 필수
        name = entity.get("name", "")
        if not isinstance(name, str) or not name.strip():
            logger.warning("엔티티 제거: name 누락 또는 빈 문자열")
            return None

        result = dict(entity)

        # 2. description 기본값
        desc = result.get("description", "")
        if not isinstance(desc, str) or not desc.strip():
            result["description"] = name
            fixes.append(f"description 누락 → '{name}'")

        # 3. object_type 검증
        ot = result.get("object_type", "")
        if ot not in EntityExtractor._VALID_OBJECT_TYPES:
            result["object_type"] = "Concept"
            fixes.append(f"object_type '{ot}' → 'Concept'")

        # 4. stance 클램프 [-1.0, 1.0]
        try:
            stance = float(result.get("stance", 0.0))
        except (TypeError, ValueError):
            stance = 0.0
            fixes.append("stance 변환 불가 → 0.0")
        clamped = max(-1.0, min(1.0, stance))
        if clamped != stance:
            fixes.append(f"stance {stance} → {clamped}")
        result["stance"] = clamped

        # 5. volatility 클램프 [0.0, 1.0]
        try:
            vol = float(result.get("volatility", 0.3))
        except (TypeError, ValueError):
            vol = 0.3
            fixes.append("volatility 변환 불가 → 0.3")
        clamped_vol = max(0.0, min(1.0, vol))
        if clamped_vol != vol:
            fixes.append(f"volatility {vol} → {clamped_vol}")
        result["volatility"] = clamped_vol

        # 6. influence_score 클램프 [0.0, 1.0]
        try:
            inf_score = float(result.get("influence_score", 0.5))
        except (TypeError, ValueError):
            inf_score = 0.5
            fixes.append("influence_score 변환 불가 → 0.5")
        clamped_inf = max(0.0, min(1.0, inf_score))
        if clamped_inf != inf_score:
            fixes.append(f"influence_score {inf_score} → {clamped_inf}")
        result["influence_score"] = clamped_inf

        if fixes:
            logger.warning(f"엔티티 '{name}' 보정: {', '.join(fixes)}")

        return result

    @staticmethod
    def _validate_and_fix_relationship(
        rel: dict,
        entity_names: set[str],
    ) -> dict | None:
        """관계 딕셔너리를 검증하고 보정한다.

        - source / target 이 entity_names 에 없으면 퍼지 매칭 시도
        - 퍼지 매칭 실패 시 None 반환 (드롭)
        - link_type 이 허용 목록 외이면 "INFLUENCES" 로 교정
        - weight 클램프 [0.0, 1.0]
        """
        fixes: list[str] = []

        # case-insensitive 조회용 맵 {lower_name: original_name}
        lower_map: dict[str, str] = {n.lower(): n for n in entity_names}

        def resolve(value: str) -> str | None:
            """엔티티 이름을 정확·퍼지 매칭으로 찾는다."""
            if not value:
                return None
            # 정확 매칭 (원본)
            if value in entity_names:
                return value
            # 대소문자 무시 정확 매칭
            lower_val = value.lower()
            if lower_val in lower_map:
                return lower_map[lower_val]
            # 퍼지: value가 엔티티 이름의 부분 문자열이거나 그 반대
            for lower_ent, orig_ent in lower_map.items():
                if lower_val in lower_ent or lower_ent in lower_val:
                    return orig_ent
            return None

        result = dict(rel)

        # source 검증
        raw_src = result.get("source", "")
        resolved_src = resolve(raw_src)
        if resolved_src is None:
            logger.warning(f"관계 제거: source '{raw_src}' 를 엔티티에서 찾을 수 없음")
            return None
        if resolved_src != raw_src:
            fixes.append(f"source '{raw_src}' → '{resolved_src}'")
        result["source"] = resolved_src

        # target 검증
        raw_tgt = result.get("target", "")
        resolved_tgt = resolve(raw_tgt)
        if resolved_tgt is None:
            logger.warning(f"관계 제거: target '{raw_tgt}' 를 엔티티에서 찾을 수 없음")
            return None
        if resolved_tgt != raw_tgt:
            fixes.append(f"target '{raw_tgt}' → '{resolved_tgt}'")
        result["target"] = resolved_tgt

        # link_type 검증
        lt = result.get("link_type", "INFLUENCES")
        if lt not in EntityExtractor._VALID_LINK_TYPES:
            result["link_type"] = "INFLUENCES"
            fixes.append(f"link_type '{lt}' → 'INFLUENCES'")

        # weight 클램프 [0.0, 1.0]
        try:
            w = float(result.get("weight", 0.5))
        except (TypeError, ValueError):
            w = 0.5
            fixes.append("weight 변환 불가 → 0.5")
        clamped_w = max(0.0, min(1.0, w))
        if clamped_w != w:
            fixes.append(f"weight {w} → {clamped_w}")
        result["weight"] = clamped_w

        if fixes:
            logger.warning(
                f"관계 '{result.get('source')}→{result.get('target')}' 보정: "
                f"{', '.join(fixes)}"
            )

        return result

    # ──────────────────── Cache I/O ────────────────────

    def _load_cache(self, key: str) -> dict[str, Any] | None:
        if not self._cache_dir:
            return None
        path = self._cache_dir / f"{key}.json"
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _save_cache(self, key: str, data: dict[str, Any]) -> None:
        if not self._cache_dir:
            return
        path = self._cache_dir / f"{key}.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning(f"캐시 저장 실패 ({key}): {e}")

    # ──────────────────── File I/O ────────────────────

    def save_results(
        self,
        ontology: DomainOntology,
        output_dir: str | Path,
    ) -> None:
        """추출 결과를 파일로 저장한다."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        ontology.save(output_dir / "comad_eye.ontology.json")

        triples_path = output_dir / "triples.jsonl"
        with open(triples_path, "w", encoding="utf-8") as f:
            for rel in ontology.relationships:
                triple = {
                    "source": rel.source_uid,
                    "target": rel.target_uid,
                    "link_type": rel.link_type,
                    "weight": rel.weight,
                    "confidence": rel.confidence,
                }
                f.write(json.dumps(triple, ensure_ascii=False) + "\n")
