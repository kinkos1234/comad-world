"""커뮤니티 요약 — LLM 기반 커뮤니티 서술 생성"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from comad_eye.graph.neo4j_client import Neo4jClient
from comad_eye.llm_client import LLMClient

logger = logging.getLogger("comadeye")

SUMMARY_SYSTEM_PROMPT = """\
커뮤니티 멤버와 관계를 분석하여 JSON으로 요약하라.
주어진 정보만 사용. 외부 지식·존재하지 않는 관계 금지.
관계가 없으면 멤버 속성만으로 요약.

출력: {"community_id":"ID","title":"한줄 제목","summary":"2~3문장 요약","key_entities":["이름"],"dominant_stance":0.0,"cohesion":0.0}
"""


class CommunitySummarizer:
    """각 커뮤니티의 LLM 기반 서술 요약을 생성한다."""

    def __init__(
        self,
        client: Neo4jClient,
        llm: LLMClient | None = None,
    ):
        self._client = client
        self._llm = llm or LLMClient()

    def summarize(
        self,
        communities: dict[str, dict[str, str]],
        tier: str = "C0",
    ) -> list[dict[str, Any]]:
        """지정된 계층의 커뮤니티를 개별 LLM 호출로 요약한다."""
        tier_communities = communities.get(tier, {})
        if not tier_communities:
            return []

        # 커뮤니티별 멤버 그룹화
        comm_members: dict[str, list[str]] = {}
        for uid, comm_id in tier_communities.items():
            comm_members.setdefault(comm_id, []).append(uid)

        logger.info(f"커뮤니티 요약 시작: {len(comm_members)}개 커뮤니티")
        summaries: list[dict[str, Any]] = []

        for comm_id, member_uids in comm_members.items():
            context = self._build_community_context(comm_id, member_uids)
            prompt = f"다음 커뮤니티를 요약하세요.\n\n{context}"

            logger.info(f"커뮤니티 {comm_id} 요약 중 (멤버 {len(member_uids)}개)")
            try:
                result = self._llm.generate_json(
                    prompt=prompt,
                    system=SUMMARY_SYSTEM_PROMPT,
                    task_type="summarization",
                )
                # 단일 커뮤니티 결과: dict 또는 {"summaries": [...]}
                if "summaries" in result:
                    summaries.extend(result["summaries"])
                else:
                    result.setdefault("community_id", comm_id)
                    summaries.append(result)
            except Exception as e:
                logger.error(f"커뮤니티 {comm_id} 요약 실패: {e}")
                # fallback: 멤버 이름만 나열
                summaries.append({
                    "community_id": comm_id,
                    "title": f"커뮤니티 {comm_id}",
                    "summary": f"멤버 {len(member_uids)}개로 구성된 커뮤니티입니다.",
                    "key_entities": member_uids[:5],
                    "dominant_stance": 0.0,
                    "cohesion": 0.0,
                })

        logger.info(f"커뮤니티 요약 완료: {len(summaries)}개")
        return summaries

    def _build_community_context(
        self, comm_id: str, member_uids: list[str]
    ) -> str:
        """커뮤니티 컨텍스트 문자열을 구성한다."""
        members_info = []
        for uid in member_uids[:10]:
            entity = self._client.get_entity(uid)
            if entity:
                members_info.append(
                    f"- {entity.get('name', uid)} "
                    f"(type={entity.get('object_type', '?')}, "
                    f"stance={entity.get('stance', 0):.2f}, "
                    f"influence={entity.get('influence_score', 0):.2f})"
                )

        rels_info = self._get_community_relations(member_uids)
        rels_text = (
            "\n".join(rels_info[:10])
            if rels_info
            else "(관계 없음 — 멤버 속성만으로 요약)"
        )
        return (
            f"커뮤니티: {comm_id} (멤버 {len(member_uids)}개)\n"
            "멤버:\n" + "\n".join(members_info) + "\n"
            "주요 관계:\n" + rels_text
        )

    def _get_community_relations(
        self, member_uids: list[str]
    ) -> list[str]:
        """커뮤니티 내 관계를 조회한다."""
        if not member_uids:
            return []

        result = self._client.query(
            "MATCH (a:Entity)-[r]->(b:Entity) "
            "WHERE a.uid IN $uids AND b.uid IN $uids "
            "AND r.expired_at IS NULL "
            "RETURN a.name AS src, type(r) AS rel, b.name AS tgt, r.weight AS w "
            "ORDER BY r.weight DESC LIMIT 10",
            uids=member_uids,
        )
        return [
            f"- {r['src']} -[{r['rel']}]-> {r['tgt']} (weight={r.get('w', 1):.2f})"
            for r in result
        ]

    def save(
        self,
        summaries: list[dict[str, Any]],
        output_path: str | Path,
    ) -> None:
        """요약 결과를 JSON으로 저장한다."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(summaries, f, ensure_ascii=False, indent=2)
