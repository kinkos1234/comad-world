"""Tests for api/routes/qa.py — Q&A session endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

fastapi = pytest.importorskip("fastapi", reason="fastapi not installed")
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api.server import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_sessions():
    """Clean up QA sessions before and after each test."""
    from api.routes.qa import _sessions
    _sessions.clear()
    yield
    _sessions.clear()


def _seed_completed_job(job_id="test_job"):
    """Insert a completed job into the pipeline store for Q&A validation."""
    from api.models import JobStatus
    from api.routes.pipeline import _jobs, _jobs_lock
    from datetime import datetime

    with _jobs_lock:
        _jobs[job_id] = {
            "status": JobStatus.COMPLETED,
            "stages": [],
            "result": {"total_rounds": 5},
            "error": None,
            "seed_text": "test seed text for QA",
            "analysis_prompt": None,
            "model_override": None,
            "lenses": None,
            "settings_override": {},
            "created_at": datetime.now().isoformat(),
        }


def _seed_running_job(job_id="running_job"):
    """Insert a running job."""
    from api.models import JobStatus
    from api.routes.pipeline import _jobs, _jobs_lock
    from datetime import datetime

    with _jobs_lock:
        _jobs[job_id] = {
            "status": JobStatus.RUNNING,
            "stages": [],
            "result": None,
            "error": None,
            "seed_text": "running job seed",
            "analysis_prompt": None,
            "model_override": None,
            "lenses": None,
            "settings_override": {},
            "created_at": datetime.now().isoformat(),
        }


@pytest.fixture(autouse=True)
def _clean_pipeline_jobs():
    """Clean pipeline jobs store."""
    from api.routes.pipeline import _jobs, _jobs_lock
    with _jobs_lock:
        _jobs.clear()
    yield
    with _jobs_lock:
        _jobs.clear()


# ---------------------------------------------------------------------------
# POST /api/qa/ask
# ---------------------------------------------------------------------------
class TestQAAsk:
    def test_ask_with_completed_job(self, client, tmp_path):
        """Asking a question with a completed job should succeed."""
        _seed_completed_job("test_job")

        mock_session = MagicMock()
        mock_session.ask.return_value = "This is the answer to your question."
        mock_session.conversation_history = [
            {"role": "user", "content": "Q?"},
            {"role": "assistant", "content": "A."},
        ]
        mock_session.save_session.return_value = None

        with patch("api.routes.qa._get_or_create_session", return_value=mock_session):
            with patch("api.routes.qa._qa_session_dir", return_value=tmp_path):
                resp = client.post("/api/qa/ask", json={
                    "question": "What are the key findings?",
                    "job_id": "test_job",
                })
                assert resp.status_code == 200
                data = resp.json()
                assert "answer" in data
                assert data["answer"] == "This is the answer to your question."
                assert "follow_ups" in data
                assert "context" in data
                assert data["context"]["job_id"] == "test_job"

    def test_ask_with_follow_ups(self, client, tmp_path):
        """When the answer contains follow-up suggestions, they should be extracted."""
        _seed_completed_job("test_job")

        answer_with_followups = (
            "Main answer here.\n\n"
            "**추가로 물어볼 수 있는 질문:**\n"
            "- What about economic factors?\n"
            "- How does this affect the population?\n"
        )
        mock_session = MagicMock()
        mock_session.ask.return_value = answer_with_followups
        mock_session.conversation_history = [{"role": "user"}, {"role": "assistant"}]
        mock_session.save_session.return_value = None

        with patch("api.routes.qa._get_or_create_session", return_value=mock_session):
            with patch("api.routes.qa._qa_session_dir", return_value=tmp_path):
                resp = client.post("/api/qa/ask", json={
                    "question": "Tell me more",
                    "job_id": "test_job",
                })
                assert resp.status_code == 200
                data = resp.json()
                assert "Main answer here." in data["answer"]
                assert len(data["follow_ups"]) == 2
                assert "economic" in data["follow_ups"][0].lower()

    def test_ask_running_job_returns_400(self, client):
        """Q&A on a non-completed job should return 400."""
        _seed_running_job("running_job")

        resp = client.post("/api/qa/ask", json={
            "question": "What happened?",
            "job_id": "running_job",
        })
        assert resp.status_code == 400

    def test_ask_nonexistent_job_still_attempts(self, client, tmp_path):
        """If job_id isn't in the pipeline store, the Q&A should still proceed
        (the job check only triggers if the job IS found and not completed)."""
        mock_session = MagicMock()
        mock_session.ask.return_value = "Answer from a freestanding session."
        mock_session.conversation_history = []
        mock_session.save_session.return_value = None

        with patch("api.routes.qa._get_or_create_session", return_value=mock_session):
            with patch("api.routes.qa._qa_session_dir", return_value=tmp_path):
                resp = client.post("/api/qa/ask", json={
                    "question": "General question?",
                    "job_id": "unknown_job",
                })
                assert resp.status_code == 200
                assert resp.json()["answer"] == "Answer from a freestanding session."

    def test_ask_empty_question_rejected(self, client):
        """Empty question should fail validation."""
        resp = client.post("/api/qa/ask", json={
            "question": "",
            "job_id": "some_job",
        })
        assert resp.status_code == 422

    def test_ask_missing_question_rejected(self, client):
        resp = client.post("/api/qa/ask", json={"job_id": "some_job"})
        assert resp.status_code == 422

    def test_ask_missing_job_id_rejected(self, client):
        resp = client.post("/api/qa/ask", json={"question": "Hello?"})
        assert resp.status_code == 422

    def test_ask_counts_turns(self, client, tmp_path):
        """The response context should include a correct turn count."""
        _seed_completed_job("test_job")

        mock_session = MagicMock()
        mock_session.ask.return_value = "Answer."
        mock_session.conversation_history = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "A2"},
        ]
        mock_session.save_session.return_value = None

        with patch("api.routes.qa._get_or_create_session", return_value=mock_session):
            with patch("api.routes.qa._qa_session_dir", return_value=tmp_path):
                resp = client.post("/api/qa/ask", json={
                    "question": "Q3",
                    "job_id": "test_job",
                })
                assert resp.status_code == 200
                assert resp.json()["context"]["turns"] == 2


# ---------------------------------------------------------------------------
# POST /api/qa/reset
# ---------------------------------------------------------------------------
class TestQAReset:
    def test_reset_existing_session(self, client):
        from api.routes.qa import _sessions
        mock_session = MagicMock()
        _sessions["job1"] = mock_session

        resp = client.post("/api/qa/reset", params={"job_id": "job1"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        mock_session.reset.assert_called_once()
        assert "job1" not in _sessions

    def test_reset_nonexistent_session(self, client):
        resp = client.post("/api/qa/reset", params={"job_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_reset_empty_job_id(self, client):
        resp = client.post("/api/qa/reset")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Session creation helper
# ---------------------------------------------------------------------------
class TestGetOrCreateSession:
    def test_creates_new_session(self, tmp_path):
        """_get_or_create_session should create a QASession when not cached."""
        from api.routes.qa import _sessions

        mock_neo4j = MagicMock()
        mock_llm = MagicMock()
        mock_qa_session = MagicMock()
        mock_qa_session.load_session.return_value = None

        # These are lazy-imported inside _get_or_create_session, so patch at source module
        with patch("utils.config.load_settings") as mock_settings:
            mock_settings.return_value = MagicMock()
            with patch("graph.neo4j_client.Neo4jClient", return_value=mock_neo4j):
                with patch("utils.llm_client.LLMClient", return_value=mock_llm):
                    with patch("narration.qa_session.QASession", return_value=mock_qa_session):
                        with patch("api.routes.qa._qa_session_dir", return_value=tmp_path):
                            with patch("api.routes.qa._job_analysis_dir", return_value=tmp_path / "analysis"):
                                from api.routes.qa import _get_or_create_session
                                session = _get_or_create_session("new_job")

                                assert session == mock_qa_session
                                assert "new_job" in _sessions
                                mock_qa_session.load_session.assert_called_once()

    def test_returns_cached_session(self, tmp_path):
        """Subsequent calls should return the same cached session."""
        from api.routes.qa import _sessions

        existing = MagicMock()
        _sessions["cached_job"] = existing

        from api.routes.qa import _get_or_create_session
        session = _get_or_create_session("cached_job")
        assert session is existing


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
class TestQAHelpers:
    def test_job_analysis_dir_with_existing_job(self, tmp_path):
        """When the job analysis dir exists, return it."""
        from api.routes.qa import _job_analysis_dir
        job_dir = tmp_path / "jobs" / "j1" / "pipeline" / "analysis"
        job_dir.mkdir(parents=True)

        with patch("api.routes.qa._JOBS_DIR", tmp_path / "jobs"):
            result = _job_analysis_dir("j1")
            assert result == job_dir

    def test_job_analysis_dir_fallback_to_global(self, tmp_path):
        """When job dir doesn't exist, fall back to data/analysis."""
        from api.routes.qa import _job_analysis_dir

        with patch("api.routes.qa._JOBS_DIR", tmp_path / "nonexistent_jobs"):
            result = _job_analysis_dir("j1")
            assert str(result) == "data/analysis"

    def test_qa_session_dir_creates_directory(self, tmp_path):
        """_qa_session_dir should create the directory."""
        from api.routes.qa import _qa_session_dir

        with patch("api.routes.qa._JOBS_DIR", tmp_path / "jobs"):
            result = _qa_session_dir("j1")
            assert result.exists()
            assert result.is_dir()
