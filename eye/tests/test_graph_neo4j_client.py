"""Tests for graph/neo4j_client.py — Neo4j driver wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from graph.neo4j_client import Neo4jClient, _validate_property_name, _SAFE_PROPERTY_NAMES


# ---------------------------------------------------------------------------
# _validate_property_name tests
# ---------------------------------------------------------------------------

class TestValidatePropertyName:
    def test_valid_names(self):
        for name in _SAFE_PROPERTY_NAMES:
            assert _validate_property_name(name) == name

    def test_invalid_name_raises(self):
        with pytest.raises(ValueError, match="Unsafe property name"):
            _validate_property_name("DROP_TABLE")

    def test_injection_attempt(self):
        with pytest.raises(ValueError):
            _validate_property_name("x} DELETE (n) WITH n SET n.{y")

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            _validate_property_name("")


# ---------------------------------------------------------------------------
# Neo4jClient construction
# ---------------------------------------------------------------------------

class TestNeo4jClientConstruction:
    @patch("graph.neo4j_client.GraphDatabase.driver")
    @patch("graph.neo4j_client.load_settings")
    def test_default_settings(self, mock_settings, mock_driver):
        mock_neo4j = MagicMock()
        mock_neo4j.uri = "bolt://localhost:7687"
        mock_neo4j.user = "neo4j"
        mock_neo4j.password = "test"
        mock_neo4j.database = "neo4j"
        mock_settings.return_value.neo4j = mock_neo4j

        Neo4jClient()
        mock_driver.assert_called_once_with(
            "bolt://localhost:7687",
            auth=("neo4j", "test"),
        )

    @patch("graph.neo4j_client.GraphDatabase.driver")
    def test_custom_settings(self, mock_driver):
        settings = MagicMock()
        settings.uri = "bolt://custom:7688"
        settings.user = "admin"
        settings.password = "secret"
        settings.database = "testdb"

        Neo4jClient(settings=settings)
        mock_driver.assert_called_once_with(
            "bolt://custom:7688",
            auth=("admin", "secret"),
        )


# ---------------------------------------------------------------------------
# Connection methods
# ---------------------------------------------------------------------------

class TestConnectionMethods:
    @patch("graph.neo4j_client.GraphDatabase.driver")
    def test_close(self, mock_driver_cls):
        mock_driver = MagicMock()
        mock_driver_cls.return_value = mock_driver
        settings = MagicMock()
        settings.uri = "bolt://x"
        settings.user = "u"
        settings.password = "p"
        settings.database = "db"

        client = Neo4jClient(settings=settings)
        client.close()
        mock_driver.close.assert_called_once()

    @patch("graph.neo4j_client.GraphDatabase.driver")
    def test_verify_connectivity_success(self, mock_driver_cls):
        mock_driver = MagicMock()
        mock_driver_cls.return_value = mock_driver
        settings = MagicMock()
        settings.uri = "bolt://x"
        settings.user = "u"
        settings.password = "p"
        settings.database = "db"

        client = Neo4jClient(settings=settings)
        assert client.verify_connectivity() is True

    @patch("graph.neo4j_client.GraphDatabase.driver")
    def test_verify_connectivity_failure(self, mock_driver_cls):
        mock_driver = MagicMock()
        mock_driver.verify_connectivity.side_effect = ConnectionError("nope")
        mock_driver_cls.return_value = mock_driver
        settings = MagicMock()
        settings.uri = "bolt://x"
        settings.user = "u"
        settings.password = "p"
        settings.database = "db"

        client = Neo4jClient(settings=settings)
        assert client.verify_connectivity() is False


# ---------------------------------------------------------------------------
# Query / Write
# ---------------------------------------------------------------------------

class TestQueryWrite:
    @pytest.fixture
    def client(self):
        with patch("graph.neo4j_client.GraphDatabase.driver") as mock_driver_cls:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_result = MagicMock()
            mock_result.__iter__ = MagicMock(return_value=iter([
                MagicMock(__iter__=lambda s: iter([("cnt", 5)]), keys=lambda: ["cnt"]),
            ]))
            mock_record = MagicMock()
            mock_record.__iter__ = lambda s: iter([("cnt", 5)])
            # Make dict(record) work
            record_dict = {"cnt": 5}
            mock_result.__iter__ = MagicMock(return_value=iter([record_dict]))

            mock_session.run.return_value = [record_dict]
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=False)
            mock_driver.session.return_value = mock_session

            mock_driver_cls.return_value = mock_driver
            settings = MagicMock()
            settings.uri = "bolt://x"
            settings.user = "u"
            settings.password = "p"
            settings.database = "db"

            c = Neo4jClient(settings=settings)
            c._mock_session = mock_session
            yield c

    def test_query_executes_cypher(self, client):
        client._mock_session.run.return_value = [{"cnt": 42}]
        client.query("MATCH (n) RETURN count(n) AS cnt")
        client._mock_session.run.assert_called()

    def test_write_executes_cypher(self, client):
        client._mock_session.run.return_value = []
        client.write("CREATE (n:Test)")
        client._mock_session.run.assert_called()


# ---------------------------------------------------------------------------
# setup_schema
# ---------------------------------------------------------------------------

class TestSetupSchema:
    @patch("graph.neo4j_client.GraphDatabase.driver")
    def test_setup_schema_runs_statements(self, mock_driver_cls):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = []
        mock_driver.session.return_value = mock_session
        mock_driver_cls.return_value = mock_driver

        settings = MagicMock()
        settings.uri = "bolt://x"
        settings.user = "u"
        settings.password = "p"
        settings.database = "db"

        client = Neo4jClient(settings=settings)
        client.setup_schema()

        # 1 constraint + 3 indexes = 4 statements
        assert mock_session.run.call_count >= 4

    @patch("graph.neo4j_client.GraphDatabase.driver")
    def test_setup_schema_handles_errors(self, mock_driver_cls):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.side_effect = Exception("already exists")
        mock_driver.session.return_value = mock_session
        mock_driver_cls.return_value = mock_driver

        settings = MagicMock()
        settings.uri = "bolt://x"
        settings.user = "u"
        settings.password = "p"
        settings.database = "db"

        client = Neo4jClient(settings=settings)
        # Should not raise despite all statements failing
        client.setup_schema()


# ---------------------------------------------------------------------------
# Entity operations
# ---------------------------------------------------------------------------

class TestEntityOperations:
    @patch("graph.neo4j_client.GraphDatabase.driver")
    def test_get_entity_found(self, mock_driver_cls):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = [{"props": {"uid": "e1", "name": "Test"}}]
        mock_driver.session.return_value = mock_session
        mock_driver_cls.return_value = mock_driver

        settings = MagicMock()
        settings.uri = "bolt://x"
        settings.user = "u"
        settings.password = "p"
        settings.database = "db"

        client = Neo4jClient(settings=settings)
        result = client.get_entity("e1")
        assert result["uid"] == "e1"

    @patch("graph.neo4j_client.GraphDatabase.driver")
    def test_get_entity_not_found(self, mock_driver_cls):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = []
        mock_driver.session.return_value = mock_session
        mock_driver_cls.return_value = mock_driver

        settings = MagicMock()
        settings.uri = "bolt://x"
        settings.user = "u"
        settings.password = "p"
        settings.database = "db"

        client = Neo4jClient(settings=settings)
        result = client.get_entity("missing")
        assert result is None

    @patch("graph.neo4j_client.GraphDatabase.driver")
    def test_update_entity_property_valid(self, mock_driver_cls):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = []
        mock_driver.session.return_value = mock_session
        mock_driver_cls.return_value = mock_driver

        settings = MagicMock()
        settings.uri = "bolt://x"
        settings.user = "u"
        settings.password = "p"
        settings.database = "db"

        client = Neo4jClient(settings=settings)
        client.update_entity_property("e1", "stance", 0.5)
        mock_session.run.assert_called()

    @patch("graph.neo4j_client.GraphDatabase.driver")
    def test_update_entity_property_unsafe(self, mock_driver_cls):
        mock_driver = MagicMock()
        mock_driver_cls.return_value = mock_driver
        settings = MagicMock()
        settings.uri = "bolt://x"
        settings.user = "u"
        settings.password = "p"
        settings.database = "db"

        client = Neo4jClient(settings=settings)
        with pytest.raises(ValueError, match="Unsafe"):
            client.update_entity_property("e1", "INJECTION", 0)


# ---------------------------------------------------------------------------
# clear_all / invalidate_cache
# ---------------------------------------------------------------------------

class TestClearAndCache:
    @patch("graph.neo4j_client.GraphDatabase.driver")
    @patch("graph.neo4j_client.graph_stats_cache")
    @patch("graph.neo4j_client.graph_counts_cache")
    def test_clear_all(self, mock_counts, mock_stats, mock_driver_cls):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = []
        mock_driver.session.return_value = mock_session
        mock_driver_cls.return_value = mock_driver

        settings = MagicMock()
        settings.uri = "bolt://x"
        settings.user = "u"
        settings.password = "p"
        settings.database = "db"

        client = Neo4jClient(settings=settings)
        client.clear_all()
        # Verify DETACH DELETE was called and cache cleared
        mock_session.run.assert_called()
        mock_stats.clear.assert_called()
        mock_counts.clear.assert_called()

    @patch("graph.neo4j_client.GraphDatabase.driver")
    @patch("graph.neo4j_client.graph_stats_cache")
    @patch("graph.neo4j_client.graph_counts_cache")
    def test_invalidate_cache(self, mock_counts, mock_stats, mock_driver_cls):
        mock_driver = MagicMock()
        mock_driver_cls.return_value = mock_driver
        settings = MagicMock()
        settings.uri = "bolt://x"
        settings.user = "u"
        settings.password = "p"
        settings.database = "db"

        client = Neo4jClient(settings=settings)
        client.invalidate_cache()
        mock_stats.clear.assert_called()
        mock_counts.clear.assert_called()


# ---------------------------------------------------------------------------
# node_count / edge_count
# ---------------------------------------------------------------------------

class TestCounts:
    @patch("graph.neo4j_client.GraphDatabase.driver")
    @patch("graph.neo4j_client.graph_counts_cache")
    def test_node_count_from_query(self, mock_cache, mock_driver_cls):
        from utils.cache import _SENTINEL
        mock_cache.get_or_sentinel.return_value = _SENTINEL

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = [{"cnt": 42}]
        mock_driver.session.return_value = mock_session
        mock_driver_cls.return_value = mock_driver

        settings = MagicMock()
        settings.uri = "bolt://x"
        settings.user = "u"
        settings.password = "p"
        settings.database = "db"

        client = Neo4jClient(settings=settings)
        count = client.node_count()
        assert count == 42

    @patch("graph.neo4j_client.GraphDatabase.driver")
    @patch("graph.neo4j_client.graph_counts_cache")
    def test_node_count_cached(self, mock_cache, mock_driver_cls):
        mock_cache.get_or_sentinel.return_value = 99

        mock_driver = MagicMock()
        mock_driver_cls.return_value = mock_driver
        settings = MagicMock()
        settings.uri = "bolt://x"
        settings.user = "u"
        settings.password = "p"
        settings.database = "db"

        client = Neo4jClient(settings=settings)
        count = client.node_count()
        assert count == 99

    @patch("graph.neo4j_client.GraphDatabase.driver")
    @patch("graph.neo4j_client.graph_counts_cache")
    def test_edge_count_active_only(self, mock_cache, mock_driver_cls):
        from utils.cache import _SENTINEL
        mock_cache.get_or_sentinel.return_value = _SENTINEL

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = [{"cnt": 10}]
        mock_driver.session.return_value = mock_session
        mock_driver_cls.return_value = mock_driver

        settings = MagicMock()
        settings.uri = "bolt://x"
        settings.user = "u"
        settings.password = "p"
        settings.database = "db"

    @patch("graph.neo4j_client.GraphDatabase.driver")
    @patch("graph.neo4j_client.graph_counts_cache")
    def test_edge_count_empty(self, mock_cache, mock_driver_cls):
        from utils.cache import _SENTINEL
        mock_cache.get_or_sentinel.return_value = _SENTINEL

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = []
        mock_driver.session.return_value = mock_session
        mock_driver_cls.return_value = mock_driver

        settings = MagicMock()
        settings.uri = "bolt://x"
        settings.user = "u"
        settings.password = "p"
        settings.database = "db"

        client = Neo4jClient(settings=settings)
        count = client.edge_count()
        assert count == 0


# ---------------------------------------------------------------------------
# SAFE_PROPERTY_NAMES constants
# ---------------------------------------------------------------------------

class TestSafePropertyNames:
    def test_contains_core_properties(self):
        assert "stance" in _SAFE_PROPERTY_NAMES
        assert "volatility" in _SAFE_PROPERTY_NAMES
        assert "influence_score" in _SAFE_PROPERTY_NAMES
        assert "community_id" in _SAFE_PROPERTY_NAMES

    def test_does_not_contain_dangerous(self):
        assert "DROP" not in _SAFE_PROPERTY_NAMES
        assert "DELETE" not in _SAFE_PROPERTY_NAMES
        assert "" not in _SAFE_PROPERTY_NAMES
