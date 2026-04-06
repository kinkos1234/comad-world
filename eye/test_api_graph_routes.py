"""Tests for api/routes/graph.py — entity listing and detail via mocked Neo4j."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

fastapi = pytest.importorskip("fastapi", reason="fastapi not installed")
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api.server import app
    return TestClient(app, raise_server_exceptions=False)


def _make_mock_client(query_return=None):
    """Create a mock Neo4jClient that returns the specified query result."""
    mock = MagicMock()
    mock.query.return_value = query_return
    mock.close.return_value = None
    return mock


# ---------------------------------------------------------------------------
# GET /api/graph/entities
# ---------------------------------------------------------------------------
class TestListEntities:
    def test_returns_list(self, client):
        mock_rows = [
            {"uid": "e1", "name": "Entity1", "object_type": "Person",
             "stance": 0.5, "volatility": 0.1, "influence_score": 0.9, "community_id": "c1"},
            {"uid": "e2", "name": "Entity2", "object_type": "Organization",
             "stance": -0.3, "volatility": 0.2, "influence_score": 0.7, "community_id": "c2"},
        ]
        mock_client = _make_mock_client(mock_rows)

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/entities")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["uid"] == "e1"
            assert data[1]["name"] == "Entity2"
            mock_client.close.assert_called_once()

    def test_returns_empty_list_when_no_entities(self, client):
        mock_client = _make_mock_client([])

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/entities")
            assert resp.status_code == 200
            assert resp.json() == []

    def test_returns_empty_list_when_query_returns_none(self, client):
        mock_client = _make_mock_client(None)

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/entities")
            assert resp.status_code == 200
            assert resp.json() == []

    def test_pagination_params(self, client):
        mock_client = _make_mock_client([])

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/entities", params={"limit": 50, "offset": 10})
            assert resp.status_code == 200
            call_args = mock_client.query.call_args
            assert call_args.kwargs["limit"] == 50
            assert call_args.kwargs["offset"] == 10

    def test_limit_clamped_to_500(self, client):
        mock_client = _make_mock_client([])

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/entities", params={"limit": 1000})
            assert resp.status_code == 200
            call_args = mock_client.query.call_args
            assert call_args.kwargs["limit"] == 500

    def test_limit_clamped_minimum_1(self, client):
        mock_client = _make_mock_client([])

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/entities", params={"limit": -5})
            assert resp.status_code == 200
            call_args = mock_client.query.call_args
            assert call_args.kwargs["limit"] == 1

    def test_negative_offset_clamped_to_0(self, client):
        mock_client = _make_mock_client([])

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/entities", params={"offset": -10})
            assert resp.status_code == 200
            call_args = mock_client.query.call_args
            assert call_args.kwargs["offset"] == 0

    def test_neo4j_error_returns_500(self, client):
        mock_client = MagicMock()
        mock_client.query.side_effect = Exception("Neo4j connection refused")
        mock_client.close.return_value = None

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/entities")
            assert resp.status_code == 500
            data = resp.json()
            assert data["code"] == "INTERNAL_ERROR"
            mock_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# GET /api/graph/relationships
# ---------------------------------------------------------------------------
class TestListRelationships:
    def test_returns_relationship_list(self, client):
        mock_rows = [
            {"source": "e1", "target": "e2", "rel_type": "INFLUENCES", "weight": 0.8},
            {"source": "e2", "target": "e3", "rel_type": "OPPOSES", "weight": None},
        ]
        mock_client = _make_mock_client(mock_rows)

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/relationships")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 2
            assert data[0]["source"] == "e1"
            assert data[0]["weight"] == 0.8
            # None weight should default to 1.0
            assert data[1]["weight"] == 1.0

    def test_returns_empty_when_no_relationships(self, client):
        mock_client = _make_mock_client([])

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/relationships")
            assert resp.status_code == 200
            assert resp.json() == []

    def test_returns_empty_when_query_returns_none(self, client):
        mock_client = _make_mock_client(None)

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/relationships")
            assert resp.status_code == 200
            assert resp.json() == []

    def test_relationship_fields_present(self, client):
        mock_rows = [
            {"source": "a", "target": "b", "rel_type": "SUPPORTS", "weight": 0.5},
        ]
        mock_client = _make_mock_client(mock_rows)

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/relationships")
            data = resp.json()
            assert set(data[0].keys()) == {"source", "target", "rel_type", "weight"}

    def test_missing_rel_type_defaults_to_empty(self, client):
        mock_rows = [
            {"source": "a", "target": "b", "weight": 0.5},
        ]
        mock_client = _make_mock_client(mock_rows)

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/relationships")
            data = resp.json()
            assert data[0]["rel_type"] == ""

    def test_neo4j_error_returns_500(self, client):
        mock_client = MagicMock()
        mock_client.query.side_effect = Exception("Connection timeout")
        mock_client.close.return_value = None

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/relationships")
            assert resp.status_code == 500
            data = resp.json()
            assert data["code"] == "INTERNAL_ERROR"
            mock_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# GET /api/graph/entity/{uid}
# ---------------------------------------------------------------------------
class TestGetEntity:
    def test_entity_found(self, client):
        mock_rows = [
            {
                "uid": "e1", "name": "TestEntity", "object_type": "Person",
                "stance": 0.5, "volatility": 0.1, "influence_score": 0.9,
                "community_id": "c1", "description": "A test entity",
                "relationships": [
                    {"related_uid": "e2", "related_name": "Other", "relation": "SUPPORTS", "weight": 0.7},
                ],
            },
        ]
        mock_client = _make_mock_client(mock_rows)

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/entity/e1")
            assert resp.status_code == 200
            data = resp.json()
            assert data["uid"] == "e1"
            assert data["name"] == "TestEntity"
            assert "timeline" in data
            assert "relationships" in data

    def test_entity_not_found_returns_404(self, client):
        mock_client = _make_mock_client([])

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/entity/nonexistent")
            assert resp.status_code == 404

    def test_entity_not_found_when_query_returns_none(self, client):
        mock_client = _make_mock_client(None)

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/entity/nonexistent")
            assert resp.status_code == 404

    def test_entity_with_job_id_and_snapshots(self, client, tmp_path, monkeypatch):
        """When job_id snapshots exist, timeline should be populated."""
        mock_rows = [
            {
                "uid": "e1", "name": "TestEntity", "object_type": "Person",
                "stance": 0.5, "volatility": 0.1, "influence_score": 0.9,
                "community_id": "c1", "description": "Test",
                "relationships": [],
            },
        ]
        mock_client = _make_mock_client(mock_rows)

        # Create snapshot files in a directory structure matching what the code expects
        snapshot_dir = tmp_path / "jobs" / "job123" / "pipeline" / "snapshots"
        snapshot_dir.mkdir(parents=True)

        snap1 = {"round": 1, "entities": [{"uid": "e1", "stance": 0.3, "volatility": 0.2}]}
        snap2 = {"round": 2, "entities": [{"uid": "e1", "stance": 0.5, "volatility": 0.1}]}
        (snapshot_dir / "round_001.json").write_text(json.dumps(snap1), encoding="utf-8")
        (snapshot_dir / "round_002.json").write_text(json.dumps(snap2), encoding="utf-8")

        # The function constructs Path(f"data/jobs/{job_id}/pipeline/snapshots").
        # We use monkeypatch to change cwd so relative paths resolve to our tmp_path.
        data_dir = tmp_path / "data"
        # Create symlink: data/jobs -> tmp_path/jobs
        data_jobs = data_dir / "jobs"
        data_dir.mkdir(exist_ok=True)
        data_jobs.symlink_to(tmp_path / "jobs")

        monkeypatch.chdir(tmp_path)

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/entity/e1", params={"job_id": "job123"})
            assert resp.status_code == 200
            data = resp.json()
            assert "timeline" in data
            assert len(data["timeline"]) == 2
            assert data["timeline"][0]["round"] == 1
            assert data["timeline"][1]["stance"] == 0.5

    def test_entity_timeline_empty_when_no_snapshots(self, client):
        """Without snapshot directories, timeline should be empty."""
        mock_rows = [
            {
                "uid": "e1", "name": "TestEntity", "object_type": "Person",
                "stance": 0.0, "volatility": 0.0, "influence_score": 0.0,
                "community_id": None, "description": None,
                "relationships": [],
            },
        ]
        mock_client = _make_mock_client(mock_rows)

        with patch("api.routes.graph._get_client", return_value=mock_client):
            # No snapshot dirs exist, so timeline should be empty
            resp = client.get("/api/graph/entity/e1")
            assert resp.status_code == 200
            data = resp.json()
            assert data["timeline"] == []

    def test_neo4j_error_returns_500(self, client):
        mock_client = MagicMock()
        mock_client.query.side_effect = Exception("Neo4j error")
        mock_client.close.return_value = None

        with patch("api.routes.graph._get_client", return_value=mock_client):
            resp = client.get("/api/graph/entity/e1")
            assert resp.status_code == 500
            data = resp.json()
            assert data["code"] == "INTERNAL_ERROR"
            mock_client.close.assert_called_once()
