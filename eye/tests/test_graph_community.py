"""Tests for graph/community.py — Leiden community detection."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from comad_eye.graph.community import CommunityDetector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    client = MagicMock()
    client.query = MagicMock()
    client.write = MagicMock()
    return client


@pytest.fixture
def detector(mock_client):
    return CommunityDetector(mock_client)


# ---------------------------------------------------------------------------
# detect() tests
# ---------------------------------------------------------------------------

class TestDetect:
    def test_no_edges_returns_empty(self, detector, mock_client):
        mock_client.query.return_value = []
        result = detector.detect()
        assert result == {"communities": {}, "tier_counts": {}}

    def test_detect_with_edges(self, detector, mock_client):
        """Test full detection pipeline with mocked igraph/leidenalg."""
        mock_client.query.return_value = [
            {"source": "a", "target": "b", "weight": 1.0},
            {"source": "b", "target": "c", "weight": 0.5},
            {"source": "a", "target": "c", "weight": 0.8},
        ]

        # Mock leidenalg.find_partition to return a simple partition
        mock_partition = [[0, 1], [2]]  # nodes a,b in comm 0; c in comm 1

        with patch("graph.community.leidenalg") as mock_leiden:
            mock_leiden.find_partition.return_value = mock_partition
            mock_leiden.RBConfigurationVertexPartition = MagicMock()

            result = detector.detect()

        assert "communities" in result
        assert "tier_counts" in result
        assert "node_count" in result
        assert result["node_count"] == 3

        # 4 tiers
        assert len(result["tier_counts"]) == 4
        for tier in ["C0", "C1", "C2", "C3"]:
            assert tier in result["communities"]

    def test_detect_writes_to_neo4j(self, detector, mock_client):
        """Verify neo4j batch writes are called."""
        mock_client.query.return_value = [
            {"source": "a", "target": "b", "weight": 1.0},
        ]

        mock_partition = [[0, 1]]
        with patch("graph.community.leidenalg") as mock_leiden:
            mock_leiden.find_partition.return_value = mock_partition
            mock_leiden.RBConfigurationVertexPartition = MagicMock()

            detector.detect()

        # At minimum, C0 batch write should have been called
        assert mock_client.write.call_count >= 1

    def test_detect_handles_none_weight(self, detector, mock_client):
        """Edges with None weight should default to 1.0."""
        mock_client.query.return_value = [
            {"source": "a", "target": "b", "weight": None},
        ]

        mock_partition = [[0, 1]]
        with patch("graph.community.leidenalg") as mock_leiden:
            mock_leiden.find_partition.return_value = mock_partition
            mock_leiden.RBConfigurationVertexPartition = MagicMock()

            result = detector.detect()
        assert result["node_count"] == 2

    def test_detect_skips_self_loops(self, detector, mock_client):
        """Self-loops (source==target) should be filtered out."""
        mock_client.query.return_value = [
            {"source": "a", "target": "a", "weight": 1.0},
            {"source": "a", "target": "b", "weight": 1.0},
        ]

        mock_partition = [[0, 1]]
        with patch("graph.community.leidenalg") as mock_leiden:
            mock_leiden.find_partition.return_value = mock_partition
            mock_leiden.RBConfigurationVertexPartition = MagicMock()

            result = detector.detect()
        assert result["node_count"] == 2


# ---------------------------------------------------------------------------
# save / load tests
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def test_save_creates_json(self, detector):
        result = {
            "communities": {"C0": {"a": "C0_0", "b": "C0_0"}},
            "tier_counts": {"C0": 1},
            "node_count": 2,
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "communities.json"
            detector.save(result, path)
            assert path.exists()
            with open(path) as f:
                loaded = json.load(f)
            assert loaded["node_count"] == 2

    def test_load_reads_json(self):
        data = {
            "communities": {"C0": {"a": "C0_0"}},
            "tier_counts": {"C0": 1},
            "node_count": 1,
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "communities.json"
            with open(path, "w") as f:
                json.dump(data, f)
            loaded = CommunityDetector.load(path)
            assert loaded["node_count"] == 1
            assert "C0" in loaded["communities"]

    def test_save_mkdir_parents(self, detector):
        result = {
            "communities": {},
            "tier_counts": {},
            "node_count": 0,
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deep" / "nested" / "result.json"
            detector.save(result, path)
            assert path.exists()


# ---------------------------------------------------------------------------
# TIER_RESOLUTIONS
# ---------------------------------------------------------------------------

class TestTierResolutions:
    def test_resolutions_count(self):
        assert len(CommunityDetector.TIER_RESOLUTIONS) == 4

    def test_resolutions_descending(self):
        res = CommunityDetector.TIER_RESOLUTIONS
        assert res == sorted(res, reverse=True)
