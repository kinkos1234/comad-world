"""대화형 Q&A 세션 — GraphRAG 기반 질의응답"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from graph.neo4j_client import Neo4jClient
from utils.embeddings import EmbeddingService
from utils.llm_client import LLMClient

logger = logging.getLogger("comadeye")

QA_SYSTEM_PROMPT = """\
당신은 시뮬레이션 분석 보고서의 Q&A 담당자입니다.
아래 제공된 그래프 탐색 결과, 커뮤니티 요약, 분석 결과를 근거로 답변하세요.

답변 규칙:
1. 제공된 데이터에 근거한 답변만 작성하세요.
2. 수치를 인용할 때는 출처(분석공간명)를 명시하세요.
3. 인과 관계를 설명할 때는 A → B → C 형식으로 체인을 명시하세요.
4. 확실하지 않은 내용은 '시뮬레이션 데이터에서 확인되지 않음'으로 표기하세요.
5. 답변은 간결하되, 구조적 근거가 반드시 포함되어야 합니다."""


class QuestionType(Enum):
    ENTITY = "entity"
    RELATIONSHIP = "relationship"
    CAUSAL = "causal"
    COMPARISON = "comparison"
    PREDICTION = "prediction"
    META = "meta"


@dataclass
class QASession:
    """대화형 Q&A 세션."""

    graph: Neo4jClient
    llm: LLMClient
    embeddings: EmbeddingService | None = None
    analysis_dir: Path = field(default_factory=lambda: Path("data/analysis"))
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    max_history: int = 10
    _analysis_cache: dict[str, Any] = field(default_factory=dict)

    def ask(self, question: str) -> str:
        """질문에 대한 답변을 생성한다."""
        # Step 1: 질문 분류
        q_type = self.classify_question(question)
        logger.info("질문 유형: %s", q_type.value)

        # Step 2: 컨텍스트 수집
        context = self._collect_context(question, q_type)

        # Step 3: LLM 답변 생성
        answer = self._generate_answer(question, context)

        # Step 4: 후처리
        answer = self._postprocess(answer, context)

        # 대화 이력 추가
        self.conversation_history.append({"role": "user", "content": question})
        self.conversation_history.append({"role": "assistant", "content": answer})

        return answer

    @staticmethod
    def classify_question(question: str) -> QuestionType:
        """질문 유형을 분류한다 (규칙 기반)."""
        q = question.lower()

        if any(w in q for w in ["왜", "원인", "때문", "이유", "인과"]):
            return QuestionType.CAUSAL
        if any(w in q for w in ["관계", "연결", "사이", "경로"]):
            return QuestionType.RELATIONSHIP
        if any(w in q for w in ["비교", "차이", "vs", "대비"]):
            return QuestionType.COMPARISON
        if any(w in q for w in ["앞으로", "계속", "예측", "전망", "되면"]):
            return QuestionType.PREDICTION
        if any(w in q for w in ["분석공간", "어떤 공간", "근거", "메타"]):
            return QuestionType.META

        return QuestionType.ENTITY

    def _collect_context(
        self, question: str, q_type: QuestionType
    ) -> dict[str, Any]:
        """3가지 소스에서 컨텍스트를 수집한다."""
        context: dict[str, Any] = {}

        # 1. 그래프 쿼리
        context["graph_result"] = self._query_graph(question, q_type)

        # 2. 벡터 검색 (임베딩 서비스 가용 시)
        if self.embeddings:
            context["relevant_chunks"] = self._vector_search(question)

        # 3. 분석 결과 참조
        context["analysis"] = self._get_relevant_analysis(q_type)

        return context

    def _query_graph(
        self, question: str, q_type: QuestionType
    ) -> list[dict[str, Any]]:
        """질문 유형에 맞는 그래프 쿼리를 실행한다."""
        # 질문에서 엔티티 이름 추출 (간단한 방식)
        entities = self._extract_entity_mentions(question)

        if q_type == QuestionType.CAUSAL and len(entities) >= 2:
            return self._query_causal_path(entities[0], entities[1])
        elif q_type == QuestionType.COMPARISON and len(entities) >= 2:
            return self._query_comparison(entities[0], entities[1])
        elif q_type == QuestionType.RELATIONSHIP and len(entities) >= 2:
            return self._query_relationship(entities[0], entities[1])
        elif entities:
            return self._query_entity(entities[0])
        else:
            return self._query_overview()

    def _extract_entity_mentions(self, question: str) -> list[str]:
        """질문에서 엔티티 이름을 추출한다."""
        all_entities = self.graph.query(
            "MATCH (n:Entity) RETURN n.name AS name, n.uid AS uid"
        )
        mentions = []
        for ent in all_entities or []:
            name = ent.get("name", "")
            if name and name in question:
                mentions.append(name)
        return mentions

    def _query_entity(self, entity_name: str) -> list[dict[str, Any]]:
        """엔티티 중심 서브그래프를 조회한다."""
        return self.graph.query(
            "MATCH (n:Entity) "
            "WHERE n.name CONTAINS $name "
            "OPTIONAL MATCH (n)-[r]-(m:Entity) "
            "RETURN n.name AS name, n.uid AS uid, n.stance AS stance, "
            "n.volatility AS volatility, n.influence_score AS influence, "
            "n.community_id AS community, "
            "collect(DISTINCT {related: m.name, relation: type(r), "
            "weight: r.weight}) AS relationships "
            "LIMIT 1",
            name=entity_name,
        ) or []

    def _query_causal_path(
        self, source: str, target: str
    ) -> list[dict[str, Any]]:
        """두 엔티티 간 인과 경로를 조회한다."""
        return self.graph.query(
            "MATCH path = shortestPath("
            "(a:Entity)-[*..5]-(b:Entity)) "
            "WHERE a.name CONTAINS $src AND b.name CONTAINS $tgt "
            "RETURN [node IN nodes(path) | node.name] AS chain, "
            "[rel IN relationships(path) | type(rel)] AS relations, "
            "length(path) AS hops "
            "LIMIT 3",
            src=source,
            tgt=target,
        ) or []

    def _query_comparison(
        self, entity_a: str, entity_b: str
    ) -> list[dict[str, Any]]:
        """두 엔티티의 속성을 비교한다."""
        return self.graph.query(
            "MATCH (a:Entity), (b:Entity) "
            "WHERE a.name CONTAINS $name_a AND b.name CONTAINS $name_b "
            "RETURN a.name AS name_a, a.stance AS stance_a, "
            "a.volatility AS vol_a, a.influence_score AS influence_a, "
            "b.name AS name_b, b.stance AS stance_b, "
            "b.volatility AS vol_b, b.influence_score AS influence_b "
            "LIMIT 1",
            name_a=entity_a,
            name_b=entity_b,
        ) or []

    def _query_relationship(
        self, entity_a: str, entity_b: str
    ) -> list[dict[str, Any]]:
        """두 엔티티 간 관계를 조회한다."""
        return self.graph.query(
            "MATCH (a:Entity)-[r]-(b:Entity) "
            "WHERE a.name CONTAINS $name_a AND b.name CONTAINS $name_b "
            "RETURN a.name AS from_name, b.name AS to_name, "
            "type(r) AS relation, r.weight AS weight "
            "LIMIT 10",
            name_a=entity_a,
            name_b=entity_b,
        ) or []

    def _query_overview(self) -> list[dict[str, Any]]:
        """전체 그래프 개요를 조회한다."""
        return self.graph.query(
            "MATCH (n:Entity) "
            "RETURN n.name AS name, n.stance AS stance, "
            "n.influence_score AS influence "
            "ORDER BY n.influence_score DESC "
            "LIMIT 10"
        ) or []

    def _vector_search(self, question: str) -> list[dict[str, Any]]:
        """벡터 검색으로 관련 청크를 찾는다."""
        if not self.embeddings:
            return []

        try:
            results = self.embeddings.search(
                query=question,
                texts=[],  # 사전 로드된 인덱스 사용
                top_k=3,
            )
            return results
        except Exception:
            return []

    def _get_relevant_analysis(self, q_type: QuestionType) -> dict[str, Any]:
        """질문 유형에 맞는 분석 결과를 로드한다."""
        type_to_file = {
            QuestionType.CAUSAL: "causal",
            QuestionType.RELATIONSHIP: "structural",
            QuestionType.COMPARISON: "structural",
            QuestionType.PREDICTION: "recursive",
            QuestionType.META: "aggregated",
            QuestionType.ENTITY: "aggregated",
        }

        file_name = type_to_file.get(q_type, "aggregated")

        if file_name in self._analysis_cache:
            return self._analysis_cache[file_name]

        path = self.analysis_dir / f"{file_name}.json"
        if not path.exists():
            return {}

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        self._analysis_cache[file_name] = data
        return data

    def _generate_answer(
        self, question: str, context: dict[str, Any]
    ) -> str:
        """LLM을 사용하여 답변을 생성한다."""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": QA_SYSTEM_PROMPT},
        ]

        # 이전 대화 이력 추가
        for turn in self.conversation_history[-self.max_history:]:
            messages.append(turn)

        # 새 질문 + 컨텍스트
        user_prompt = (
            f"질문: {question}\n\n"
            f"[그래프 탐색 결과]\n{json.dumps(context.get('graph_result', []), ensure_ascii=False, default=str)}\n\n"
            f"[분석 결과]\n{json.dumps(context.get('analysis', {}), ensure_ascii=False, default=str)[:2000]}"
        )

        return self.llm.generate(
            system=QA_SYSTEM_PROMPT,
            prompt=user_prompt,
        ) or "답변을 생성할 수 없습니다."

    def _postprocess(self, answer: str, context: dict[str, Any]) -> str:
        """답변을 후처리한다."""
        # 후속 질문 제안
        follow_ups = self._suggest_follow_ups(context)
        if follow_ups:
            answer += "\n\n**추가로 물어볼 수 있는 질문:**\n"
            for q in follow_ups:
                answer += f"- {q}\n"

        return answer

    def _suggest_follow_ups(
        self, context: dict[str, Any]
    ) -> list[str]:
        """후속 질문을 제안한다."""
        suggestions: list[str] = []
        graph_result = context.get("graph_result", [])

        if graph_result and isinstance(graph_result, list):
            first = graph_result[0] if graph_result else {}

            # 관계가 있는 경우
            relationships = first.get("relationships", [])
            if relationships and isinstance(relationships, list):
                related = relationships[0]
                if isinstance(related, dict) and related.get("related"):
                    suggestions.append(
                        f"{related['related']}와의 관계를 더 자세히 알려줘"
                    )

            # 커뮤니티 정보가 있는 경우
            community = first.get("community")
            if community:
                suggestions.append(
                    f"커뮤니티 {community}에 속한 다른 엔티티들은?"
                )

        # 분석 결과 기반 제안
        analysis = context.get("analysis", {})
        findings = analysis.get("key_findings", [])
        if findings and len(findings) > 1:
            suggestions.append(
                f"{findings[1].get('finding', '')[:30]}...에 대해 자세히 설명해줘"
            )

        return suggestions[:3]

    # --- Session Persistence ---

    def save_session(self, path: Path | str | None = None) -> Path:
        """대화 이력을 JSON 파일로 저장한다."""
        save_path = Path(path) if path else self.analysis_dir / "qa_session.json"
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(self.conversation_history, f, ensure_ascii=False, indent=2)
        logger.info("Q&A 세션 저장: %s (%d턴)", save_path, len(self.conversation_history) // 2)
        return save_path

    def load_session(self, path: Path | str | None = None) -> int:
        """저장된 대화 이력을 복원한다. 복원된 턴 수를 반환."""
        load_path = Path(path) if path else self.analysis_dir / "qa_session.json"
        if not load_path.exists():
            return 0
        try:
            with open(load_path, encoding="utf-8") as f:
                history = json.load(f)
            if isinstance(history, list):
                self.conversation_history = history
                turns = len(history) // 2
                logger.info("Q&A 세션 복원: %s (%d턴)", load_path, turns)
                return turns
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Q&A 세션 복원 실패: %s", e)
        return 0

    def reset(self) -> None:
        """대화 이력을 초기화한다."""
        self.conversation_history.clear()
        self._analysis_cache.clear()
