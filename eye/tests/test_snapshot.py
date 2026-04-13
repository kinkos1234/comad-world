"""Tests for simulation/snapshot.py — snapshot writer and invariant checks."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from comad_eye.simulation.snapshot import SnapshotWriter


# ---------------------------------------------------------------------------
# Helper to create a mocked SnapshotWriter
# ---------------------------------------------------------------------------

def _make_writer(tmp_path: Path, stats=None, query_results=None) -> SnapshotWriter:
    """Create a SnapshotWriter with a mocked Neo4j client."""
    client = MagicMock()
    client.get_graph_stats.return_value = stats or {
        "node_count": 10,
        "edge_count": 15,
        "avg_volatility": 0.3,
        "avg_stance": 0.1,
        "relationship_distribution": {"INFLUENCES": 10, "OPPOSES": 5},
    }
    client.query.return_value = query_results or []
    return SnapshotWriter(client, output_dir=str(tmp_path))


# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------

class TestSave:
    def test_creates_snapshot_file(self, tmp_path):
        writer = _make_writer(tmp_path)
        path = writer.save(round_num=1, changes={})
        assert path.exists()
        assert path.name == "round_001.jsonl"

    def test_snapshot_content_structure(self, tmp_path):
        writer = _make_writer(tmp_path)
        path = writer.save(round_num=3, changes={"propagation": [{"a": 1}]})

        with open(path) as f:
            data = json.loads(f.readline())

        assert data["round"] == 3
        assert "timestamp" in data
        assert data["propagation_effects"] == 1
        assert "summary" in data
        assert "changes" in data

    def test_empty_changes(self, tmp_path):
        writer = _make_writer(tmp_path)
        path = writer.save(round_num=0, changes={})

        with open(path) as f:
            data = json.loads(f.readline())

        assert data["events_injected"] == 0
        assert data["propagation_effects"] == 0
        assert data["meta_edges_fired"] == 0
        assert data["actions_executed"] == 0
        assert data["community_migrations"] == 0

    def test_round_number_formatting(self, tmp_path):
        writer = _make_writer(tmp_path)
        path = writer.save(round_num=42, changes={})
        assert path.name == "round_042.jsonl"

    def test_creates_output_directory(self, tmp_path):
        nested = tmp_path / "nested" / "dir"
        SnapshotWriter(MagicMock(), output_dir=str(nested))
        assert nested.exists()


# ---------------------------------------------------------------------------
# _serialize_changes
# ---------------------------------------------------------------------------

class TestSerializeChanges:
    def test_events_serialization(self, tmp_path):
        writer = _make_writer(tmp_path)

        mock_event = MagicMock()
        mock_event.uid = "e1"
        mock_event.name = "Event 1"
        mock_event.magnitude = 0.8

        changes = {"events": [mock_event]}
        result = writer._serialize_changes(changes)

        assert len(result["events"]) == 1
        assert result["events"][0]["uid"] == "e1"
        assert result["events"][0]["magnitude"] == 0.8

    def test_actions_serialization(self, tmp_path):
        writer = _make_writer(tmp_path)
        changes = {
            "actions": [
                {"action": "lobby", "actor": "uid1", "actor_name": "Actor1"},
            ]
        }
        result = writer._serialize_changes(changes)
        assert result["actions"][0]["action"] == "lobby"
        assert result["actions"][0]["actor"] == "uid1"

    def test_propagation_truncated(self, tmp_path):
        writer = _make_writer(tmp_path)
        changes = {"propagation": list(range(50))}
        result = writer._serialize_changes(changes)
        assert len(result["propagation"]) == 20  # capped

    def test_meta_edges_truncated(self, tmp_path):
        writer = _make_writer(tmp_path)
        changes = {"meta_edges": list(range(30))}
        result = writer._serialize_changes(changes)
        assert len(result["meta_edges"]) == 20

    def test_migrations_passed_through(self, tmp_path):
        writer = _make_writer(tmp_path)
        changes = {"migrations": [{"from": "a", "to": "b"}]}
        result = writer._serialize_changes(changes)
        assert result["migrations"] == [{"from": "a", "to": "b"}]

    def test_empty_changes(self, tmp_path):
        writer = _make_writer(tmp_path)
        result = writer._serialize_changes({})
        assert result == {}


# ---------------------------------------------------------------------------
# _get_summary
# ---------------------------------------------------------------------------

class TestGetSummary:
    def test_returns_expected_keys(self, tmp_path):
        writer = _make_writer(tmp_path)
        summary = writer._get_summary()

        assert "node_count" in summary
        assert "active_edge_count" in summary
        assert "avg_volatility" in summary
        assert "avg_stance" in summary
        assert "stance_distribution" in summary
        assert "community_count" in summary

    def test_uses_graph_stats(self, tmp_path):
        writer = _make_writer(
            tmp_path,
            stats={"node_count": 42, "edge_count": 100, "avg_volatility": 0.5, "avg_stance": 0.2},
        )
        summary = writer._get_summary()
        assert summary["node_count"] == 42
        assert summary["active_edge_count"] == 100

    def test_empty_query_results(self, tmp_path):
        writer = _make_writer(tmp_path, query_results=[])
        summary = writer._get_summary()
        assert summary["stance_distribution"] == {}
        assert summary["community_count"] == 0


# ---------------------------------------------------------------------------
# check_invariants
# ---------------------------------------------------------------------------

class TestCheckInvariants:
    def test_no_violations(self, tmp_path):
        client = MagicMock()
        client.query.return_value = []
        writer = SnapshotWriter(client, output_dir=str(tmp_path))

        violations = writer.check_invariants()
        assert violations == []

    def test_stance_violation(self, tmp_path):
        client = MagicMock()

        def query_side_effect(cypher, **kwargs):
            if "stance < -1.0" in cypher:
                return [{"uid": "bad_entity", "val": -1.5}]
            if "volatility < 0.0" in cypher:
                return []
            if "(n)-[r]->(n)" in cypher:
                return [{"cnt": 0}]
            return []

        client.query.side_effect = query_side_effect
        writer = SnapshotWriter(client, output_dir=str(tmp_path))

        violations = writer.check_invariants()
        assert len(violations) == 1
        assert "stance" in violations[0]
        assert "bad_entity" in violations[0]

    def test_volatility_violation(self, tmp_path):
        client = MagicMock()

        def query_side_effect(cypher, **kwargs):
            if "stance" in cypher:
                return []
            if "volatility" in cypher:
                return [{"uid": "vol_entity", "val": 1.5}]
            if "(n)-[r]->(n)" in cypher:
                return [{"cnt": 0}]
            return []

        client.query.side_effect = query_side_effect
        writer = SnapshotWriter(client, output_dir=str(tmp_path))

        violations = writer.check_invariants()
        assert any("volatility" in v for v in violations)

    def test_self_reference_violation(self, tmp_path):
        client = MagicMock()

        def query_side_effect(cypher, **kwargs):
            if "stance" in cypher:
                return []
            if "volatility" in cypher:
                return []
            if "(n)-[r]->(n)" in cypher:
                return [{"cnt": 3}]
            return []

        client.query.side_effect = query_side_effect
        writer = SnapshotWriter(client, output_dir=str(tmp_path))

        violations = writer.check_invariants()
        assert any("자기참조" in v for v in violations)

    def test_multiple_violations(self, tmp_path):
        client = MagicMock()

        def query_side_effect(cypher, **kwargs):
            if "stance" in cypher:
                return [{"uid": "e1", "val": 2.0}]
            if "volatility" in cypher:
                return [{"uid": "e2", "val": -0.5}]
            if "(n)-[r]->(n)" in cypher:
                return [{"cnt": 1}]
            return []

        client.query.side_effect = query_side_effect
        writer = SnapshotWriter(client, output_dir=str(tmp_path))

        violations = writer.check_invariants()
        assert len(violations) == 3


# ---------------------------------------------------------------------------
# load_snapshots
# ---------------------------------------------------------------------------

class TestLoadSnapshots:
    def test_load_empty_directory(self, tmp_path):
        snapshots = SnapshotWriter.load_snapshots(tmp_path)
        assert snapshots == []

    def test_load_single_snapshot(self, tmp_path):
        data = {"round": 1, "events_injected": 2}
        path = tmp_path / "round_001.jsonl"
        path.write_text(json.dumps(data) + "\n")

        snapshots = SnapshotWriter.load_snapshots(tmp_path)
        assert len(snapshots) == 1
        assert snapshots[0]["round"] == 1

    def test_load_multiple_sorted(self, tmp_path):
        for i in [3, 1, 2]:
            path = tmp_path / f"round_{i:03d}.jsonl"
            path.write_text(json.dumps({"round": i}) + "\n")

        snapshots = SnapshotWriter.load_snapshots(tmp_path)
        assert len(snapshots) == 3
        assert [s["round"] for s in snapshots] == [1, 2, 3]

    def test_load_ignores_non_snapshot_files(self, tmp_path):
        (tmp_path / "round_001.jsonl").write_text(json.dumps({"round": 1}) + "\n")
        (tmp_path / "other.txt").write_text("not a snapshot\n")

        snapshots = SnapshotWriter.load_snapshots(tmp_path)
        assert len(snapshots) == 1

    def test_accepts_string_path(self, tmp_path):
        (tmp_path / "round_001.jsonl").write_text(json.dumps({"round": 1}) + "\n")
        snapshots = SnapshotWriter.load_snapshots(str(tmp_path))
        assert len(snapshots) == 1
