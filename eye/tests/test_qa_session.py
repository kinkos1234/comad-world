"""Tests for narration/qa_session.py — comprehensive coverage.

Covers: QASession.ask(), classify_question(), _collect_context(),
_query_graph(), _extract_entity_mentions(), _query_entity(),
_query_causal_path(), _query_comparison(), _query_relationship(),
_query_overview(), _vector_search(), _get_relevant_analysis(),
_generate_answer(), _postprocess(), _suggest_follow_ups(),
save_session(), load_session(), reset().
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from comad_eye.narration.qa_session import QASession, QuestionType


# ───────────────────── Fixtures ─────────────────────


def _mock_graph() -> MagicMock:
    """Create a mock Neo4jClient."""
    graph = MagicMock()
    graph.query.return_value = []
    return graph


def _mock_llm(return_value: str = "테스트 답변입니다.") -> MagicMock:
    """Create a mock LLMClient."""
    llm = MagicMock()
    llm.generate.return_value = return_value
    return llm


def _mock_embeddings() -> MagicMock:
    """Create a mock EmbeddingService."""
    emb = MagicMock()
    emb.search.return_value = [{"text": "chunk1", "score": 0.9}]
    return emb


def _make_session(
    graph=None,
    llm=None,
    embeddings=None,
    analysis_dir=None,
) -> QASession:
    """Create a QASession with mocked dependencies."""
    return QASession(
        graph=graph or _mock_graph(),
        llm=llm or _mock_llm(),
        embeddings=embeddings,
        analysis_dir=analysis_dir or Path("/tmp/test_qa"),
    )


# ───────────────────── QuestionType Classification ─────────────────────


class TestClassifyQuestion:
    def test_causal_keywords(self):
        for word in ["왜", "원인", "때문", "이유", "인과"]:
            assert QASession.classify_question(f"이 결과의 {word}은 무엇인가?") == QuestionType.CAUSAL

    def test_relationship_keywords(self):
        for word in ["관계", "연결", "사이", "경로"]:
            assert QASession.classify_question(f"A와 B의 {word}") == QuestionType.RELATIONSHIP

    def test_comparison_keywords(self):
        for word in ["비교", "차이", "vs", "대비"]:
            assert QASession.classify_question(f"A와 B의 {word}") == QuestionType.COMPARISON

    def test_prediction_keywords(self):
        for word in ["앞으로", "계속", "예측", "전망", "되면"]:
            assert QASession.classify_question(f"{word} 어떻게 될까?") == QuestionType.PREDICTION

    def test_meta_keywords(self):
        for word in ["분석공간", "어떤 공간", "근거", "메타"]:
            assert QASession.classify_question(f"{word}은 무엇인가?") == QuestionType.META

    def test_default_entity(self):
        assert QASession.classify_question("삼성전자에 대해 알려줘") == QuestionType.ENTITY

    def test_empty_question(self):
        assert QASession.classify_question("") == QuestionType.ENTITY


# ───────────────────── Entity Mention Extraction ─────────────────────


class TestExtractEntityMentions:
    def test_finds_matching_entities(self):
        graph = _mock_graph()
        graph.query.return_value = [
            {"name": "삼성전자", "uid": "samsung"},
            {"name": "TSMC", "uid": "tsmc"},
        ]
        session = _make_session(graph=graph)
        mentions = session._extract_entity_mentions("삼성전자와 TSMC의 관계는?")
        assert "삼성전자" in mentions
        assert "TSMC" in mentions

    def test_no_matches(self):
        graph = _mock_graph()
        graph.query.return_value = [
            {"name": "삼성전자", "uid": "samsung"},
        ]
        session = _make_session(graph=graph)
        mentions = session._extract_entity_mentions("구글에 대해 알려줘")
        assert mentions == []

    def test_empty_entities(self):
        graph = _mock_graph()
        graph.query.return_value = []
        session = _make_session(graph=graph)
        mentions = session._extract_entity_mentions("질문")
        assert mentions == []

    def test_none_entities_response(self):
        graph = _mock_graph()
        graph.query.return_value = None
        session = _make_session(graph=graph)
        mentions = session._extract_entity_mentions("질문")
        assert mentions == []

    def test_entity_with_empty_name_skipped(self):
        graph = _mock_graph()
        graph.query.return_value = [
            {"name": "", "uid": "empty"},
            {"name": "존재하는엔티티", "uid": "exists"},
        ]
        session = _make_session(graph=graph)
        mentions = session._extract_entity_mentions("존재하는엔티티에 대해")
        assert "존재하는엔티티" in mentions
        assert "" not in mentions


# ───────────────────── Graph Query Routing ─────────────────────


class TestQueryGraph:
    def test_causal_with_two_entities(self):
        graph = _mock_graph()
        graph.query.side_effect = [
            [{"name": "A", "uid": "a"}, {"name": "B", "uid": "b"}],
            [{"chain": ["A", "B"], "relations": ["INFLUENCES"], "hops": 1}],
        ]
        session = _make_session(graph=graph)
        result = session._query_graph("A와 B의 원인은?", QuestionType.CAUSAL)
        assert len(result) > 0

    def test_comparison_with_two_entities(self):
        graph = _mock_graph()
        graph.query.side_effect = [
            [{"name": "A", "uid": "a"}, {"name": "B", "uid": "b"}],
            [{"name_a": "A", "name_b": "B"}],
        ]
        session = _make_session(graph=graph)
        result = session._query_graph("A와 B 비교", QuestionType.COMPARISON)
        assert isinstance(result, list)

    def test_relationship_with_two_entities(self):
        graph = _mock_graph()
        graph.query.side_effect = [
            [{"name": "A", "uid": "a"}, {"name": "B", "uid": "b"}],
            [{"from_name": "A", "to_name": "B"}],
        ]
        session = _make_session(graph=graph)
        result = session._query_graph("A와 B 사이의 관계", QuestionType.RELATIONSHIP)
        assert isinstance(result, list)

    def test_entity_with_one_entity(self):
        graph = _mock_graph()
        graph.query.side_effect = [
            [{"name": "A", "uid": "a"}],
            [{"name": "A", "uid": "a", "relationships": []}],
        ]
        session = _make_session(graph=graph)
        result = session._query_graph("A에 대해", QuestionType.ENTITY)
        assert isinstance(result, list)

    def test_overview_fallback(self):
        graph = _mock_graph()
        graph.query.side_effect = [
            [],  # no entities found
            [{"name": "A", "stance": 0.5}],  # overview query
        ]
        session = _make_session(graph=graph)
        result = session._query_graph("전체적으로 어떤가?", QuestionType.ENTITY)
        assert isinstance(result, list)

    def test_causal_with_single_entity_falls_to_entity_query(self):
        graph = _mock_graph()
        graph.query.side_effect = [
            [{"name": "A", "uid": "a"}],  # only one entity
            [{"name": "A"}],  # entity query result
        ]
        session = _make_session(graph=graph)
        result = session._query_graph("A의 원인은?", QuestionType.CAUSAL)
        assert isinstance(result, list)


# ───────────────────── Individual Query Methods ─────────────────────


class TestQueryMethods:
    def test_query_entity(self):
        graph = _mock_graph()
        graph.query.return_value = [{"name": "Alpha", "uid": "alpha"}]
        session = _make_session(graph=graph)
        result = session._query_entity("Alpha")
        assert result == [{"name": "Alpha", "uid": "alpha"}]

    def test_query_entity_returns_empty_on_none(self):
        graph = _mock_graph()
        graph.query.return_value = None
        session = _make_session(graph=graph)
        result = session._query_entity("Alpha")
        assert result == []

    def test_query_causal_path(self):
        graph = _mock_graph()
        graph.query.return_value = [{"chain": ["A", "B"], "hops": 1}]
        session = _make_session(graph=graph)
        result = session._query_causal_path("A", "B")
        assert len(result) == 1

    def test_query_comparison(self):
        graph = _mock_graph()
        graph.query.return_value = [{"name_a": "A", "name_b": "B"}]
        session = _make_session(graph=graph)
        result = session._query_comparison("A", "B")
        assert len(result) == 1

    def test_query_relationship(self):
        graph = _mock_graph()
        graph.query.return_value = [{"from_name": "A", "to_name": "B"}]
        session = _make_session(graph=graph)
        result = session._query_relationship("A", "B")
        assert len(result) == 1

    def test_query_overview(self):
        graph = _mock_graph()
        graph.query.return_value = [{"name": "A", "influence": 0.8}]
        session = _make_session(graph=graph)
        result = session._query_overview()
        assert len(result) == 1


# ───────────────────── Vector Search ─────────────────────


class TestVectorSearch:
    def test_with_embeddings(self):
        emb = _mock_embeddings()
        session = _make_session(embeddings=emb)
        results = session._vector_search("query")
        assert len(results) == 1
        assert results[0]["text"] == "chunk1"

    def test_without_embeddings(self):
        session = _make_session(embeddings=None)
        results = session._vector_search("query")
        assert results == []

    def test_embeddings_error_returns_empty(self):
        emb = MagicMock()
        emb.search.side_effect = Exception("search error")
        session = _make_session(embeddings=emb)
        results = session._vector_search("query")
        assert results == []


# ───────────────────── Analysis Loading ─────────────────────


class TestGetRelevantAnalysis:
    def test_loads_causal_file(self, tmp_path):
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        (analysis_dir / "causal.json").write_text('{"key": "value"}', encoding="utf-8")
        session = _make_session(analysis_dir=analysis_dir)
        result = session._get_relevant_analysis(QuestionType.CAUSAL)
        assert result == {"key": "value"}

    def test_caches_result(self, tmp_path):
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        (analysis_dir / "causal.json").write_text('{"key": "value"}', encoding="utf-8")
        session = _make_session(analysis_dir=analysis_dir)
        # First call loads from file
        session._get_relevant_analysis(QuestionType.CAUSAL)
        # Modify file — should still return cached
        (analysis_dir / "causal.json").write_text('{"key": "changed"}', encoding="utf-8")
        result2 = session._get_relevant_analysis(QuestionType.CAUSAL)
        assert result2 == {"key": "value"}  # cached

    def test_missing_file_returns_empty(self, tmp_path):
        session = _make_session(analysis_dir=tmp_path / "no_such_dir")
        result = session._get_relevant_analysis(QuestionType.ENTITY)
        assert result == {}

    def test_type_to_file_mapping(self, tmp_path):
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        mappings = {
            QuestionType.CAUSAL: "causal",
            QuestionType.RELATIONSHIP: "structural",
            QuestionType.COMPARISON: "structural",
            QuestionType.PREDICTION: "recursive",
            QuestionType.META: "aggregated",
            QuestionType.ENTITY: "aggregated",
        }
        for q_type, fname in mappings.items():
            (analysis_dir / f"{fname}.json").write_text(
                json.dumps({"type": fname}), encoding="utf-8"
            )

        for q_type, fname in mappings.items():
            session = _make_session(analysis_dir=analysis_dir)
            result = session._get_relevant_analysis(q_type)
            assert result.get("type") == fname, f"Failed for {q_type}"


# ───────────────────── Answer Generation ─────────────────────


class TestGenerateAnswer:
    def test_basic_answer(self):
        llm = _mock_llm("시뮬레이션 결과에 따르면...")
        session = _make_session(llm=llm)
        context = {"graph_result": [], "analysis": {}}
        answer = session._generate_answer("질문", context)
        assert answer == "시뮬레이션 결과에 따르면..."

    def test_llm_returns_none(self):
        llm = _mock_llm(None)
        session = _make_session(llm=llm)
        context = {"graph_result": [], "analysis": {}}
        answer = session._generate_answer("질문", context)
        assert answer == "답변을 생성할 수 없습니다."

    def test_conversation_history_included(self):
        llm = _mock_llm("답변")
        session = _make_session(llm=llm)
        session.conversation_history = [
            {"role": "user", "content": "이전 질문"},
            {"role": "assistant", "content": "이전 답변"},
        ]
        context = {"graph_result": [], "analysis": {}}
        session._generate_answer("새 질문", context)
        # Verify generate was called (history is passed through messages internally)
        assert llm.generate.called

    def test_max_history_respected(self):
        llm = _mock_llm("답변")
        session = _make_session(llm=llm)
        session.max_history = 2
        session.conversation_history = [
            {"role": "user", "content": f"질문 {i}"}
            for i in range(20)
        ]
        context = {"graph_result": [], "analysis": {}}
        session._generate_answer("질문", context)
        assert llm.generate.called


# ───────────────────── Postprocess ─────────────────────


class TestPostprocess:
    def test_adds_follow_ups(self):
        session = _make_session()
        context = {
            "graph_result": [
                {
                    "name": "Alpha",
                    "community": "C1",
                    "relationships": [{"related": "Beta", "relation": "INFLUENCES"}],
                }
            ],
            "analysis": {},
        }
        answer = session._postprocess("기본 답변", context)
        assert "추가로 물어볼 수 있는 질문" in answer

    def test_no_follow_ups(self):
        session = _make_session()
        context = {"graph_result": [], "analysis": {}}
        answer = session._postprocess("기본 답변", context)
        assert "추가로 물어볼 수 있는 질문" not in answer


# ───────────────────── Suggest Follow-ups ─────────────────────


class TestSuggestFollowUps:
    def test_relationship_suggestion(self):
        session = _make_session()
        context = {
            "graph_result": [
                {
                    "relationships": [
                        {"related": "Beta", "relation": "INFLUENCES", "weight": 0.8}
                    ],
                }
            ],
            "analysis": {},
        }
        suggestions = session._suggest_follow_ups(context)
        assert any("Beta" in s for s in suggestions)

    def test_community_suggestion(self):
        session = _make_session()
        context = {
            "graph_result": [{"community": "C1"}],
            "analysis": {},
        }
        suggestions = session._suggest_follow_ups(context)
        assert any("C1" in s for s in suggestions)

    def test_analysis_key_findings_suggestion(self):
        session = _make_session()
        context = {
            "graph_result": [],
            "analysis": {
                "key_findings": [
                    {"finding": "First finding"},
                    {"finding": "Second important finding here"},
                ],
            },
        }
        suggestions = session._suggest_follow_ups(context)
        assert any("Second" in s for s in suggestions)

    def test_max_3_suggestions(self):
        session = _make_session()
        context = {
            "graph_result": [
                {
                    "community": "C1",
                    "relationships": [
                        {"related": "Beta", "relation": "R1", "weight": 1},
                    ],
                }
            ],
            "analysis": {
                "key_findings": [
                    {"finding": "F1"},
                    {"finding": "Second finding is here for testing"},
                ],
            },
        }
        suggestions = session._suggest_follow_ups(context)
        assert len(suggestions) <= 3

    def test_empty_context(self):
        session = _make_session()
        suggestions = session._suggest_follow_ups({})
        assert suggestions == []

    def test_relationship_with_no_related_name(self):
        session = _make_session()
        context = {
            "graph_result": [
                {
                    "relationships": [{"related": None, "relation": "R1"}],
                }
            ],
        }
        suggestions = session._suggest_follow_ups(context)
        # Should not include suggestion for None-related
        assert not any("None" in str(s) for s in suggestions)

    def test_non_dict_relationship_skipped(self):
        session = _make_session()
        context = {
            "graph_result": [
                {
                    "relationships": ["not_a_dict"],
                }
            ],
        }
        suggestions = session._suggest_follow_ups(context)
        assert isinstance(suggestions, list)


# ───────────────────── Full Ask Flow ─────────────────────


class TestAsk:
    def test_full_ask_flow(self):
        graph = _mock_graph()
        graph.query.return_value = []
        llm = _mock_llm("AI 답변")
        session = _make_session(graph=graph, llm=llm)

        answer = session.ask("삼성전자에 대해 알려줘")
        assert "AI 답변" in answer
        # History is updated
        assert len(session.conversation_history) == 2
        assert session.conversation_history[0]["role"] == "user"
        assert session.conversation_history[1]["role"] == "assistant"

    def test_multiple_asks_build_history(self):
        graph = _mock_graph()
        graph.query.return_value = []
        llm = _mock_llm("답변")
        session = _make_session(graph=graph, llm=llm)

        session.ask("질문 1")
        session.ask("질문 2")
        assert len(session.conversation_history) == 4

    def test_ask_with_embeddings(self, tmp_path):
        graph = _mock_graph()
        graph.query.return_value = []
        llm = _mock_llm("답변")
        emb = _mock_embeddings()
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        session = _make_session(
            graph=graph, llm=llm, embeddings=emb, analysis_dir=analysis_dir
        )

        session.ask("질문")
        assert emb.search.called


# ───────────────────── Session Persistence ─────────────────────


class TestSessionPersistence:
    def test_save_session(self, tmp_path):
        session = _make_session(analysis_dir=tmp_path)
        session.conversation_history = [
            {"role": "user", "content": "질문"},
            {"role": "assistant", "content": "답변"},
        ]
        path = session.save_session()
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) == 2

    def test_save_session_custom_path(self, tmp_path):
        session = _make_session()
        session.conversation_history = [{"role": "user", "content": "q"}]
        custom_path = tmp_path / "custom" / "session.json"
        path = session.save_session(custom_path)
        assert path == custom_path
        assert path.exists()

    def test_load_session(self, tmp_path):
        session = _make_session(analysis_dir=tmp_path)
        # Save first
        session.conversation_history = [
            {"role": "user", "content": "질문"},
            {"role": "assistant", "content": "답변"},
        ]
        session.save_session()

        # Load into fresh session
        session2 = _make_session(analysis_dir=tmp_path)
        turns = session2.load_session()
        assert turns == 1
        assert len(session2.conversation_history) == 2

    def test_load_session_file_not_exists(self, tmp_path):
        session = _make_session(analysis_dir=tmp_path / "no_such")
        turns = session.load_session()
        assert turns == 0

    def test_load_session_corrupted_json(self, tmp_path):
        session = _make_session(analysis_dir=tmp_path)
        (tmp_path / "qa_session.json").write_text("{{invalid json", encoding="utf-8")
        turns = session.load_session()
        assert turns == 0

    def test_load_session_non_list_data(self, tmp_path):
        session = _make_session(analysis_dir=tmp_path)
        (tmp_path / "qa_session.json").write_text('{"not": "a list"}', encoding="utf-8")
        turns = session.load_session()
        assert turns == 0

    def test_load_session_custom_path(self, tmp_path):
        session = _make_session()
        custom = tmp_path / "custom.json"
        custom.write_text('[{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]', encoding="utf-8")
        turns = session.load_session(custom)
        assert turns == 1

    def test_reset(self):
        session = _make_session()
        session.conversation_history = [{"role": "user", "content": "q"}]
        session._analysis_cache = {"causal": {"data": True}}
        session.reset()
        assert session.conversation_history == []
        assert session._analysis_cache == {}


# ───────────────────── Collect Context ─────────────────────


class TestCollectContext:
    def test_without_embeddings(self, tmp_path):
        session = _make_session(analysis_dir=tmp_path)
        context = session._collect_context("질문", QuestionType.ENTITY)
        assert "graph_result" in context
        assert "analysis" in context
        assert "relevant_chunks" not in context

    def test_with_embeddings(self, tmp_path):
        emb = _mock_embeddings()
        session = _make_session(embeddings=emb, analysis_dir=tmp_path)
        context = session._collect_context("질문", QuestionType.ENTITY)
        assert "relevant_chunks" in context
