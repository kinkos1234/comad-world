"""Tests for analysis/base.py — SimulationData and AnalysisSpace."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from analysis.base import AnalysisSpace, SimulationData


def _write_snapshots(tmp_dir: Path, snapshots: list[dict[str, Any]]) -> None:
    """Write snapshot dicts as round_NNN.jsonl files for from_snapshots."""
    for i, snap in enumerate(snapshots, start=1):
        path = tmp_dir / f"round_{i:03d}.jsonl"
        path.write_text(json.dumps(snap) + "\n", encoding="utf-8")


# ── SimulationData construction ──


class TestSimulationDataInit:
    def test_default_empty(self):
        sd = SimulationData()
        assert sd.snapshots == []
        assert sd.events_log == []
        assert sd.actions_log == []
        assert sd.meta_edges_log == []
        assert sd.communities_initial == {}
        assert sd.communities_final == {}
        assert sd.community_migrations == []
        assert sd.graph is None

    def test_custom_fields(self):
        sd = SimulationData(
            snapshots=[{"round": 0}],
            events_log=[{"uid": "e1"}],
            graph=MagicMock(),
        )
        assert len(sd.snapshots) == 1
        assert len(sd.events_log) == 1
        assert sd.graph is not None


# ── SimulationData.from_snapshots ──


class TestFromSnapshots:
    def test_empty_snapshots_returns_empty_data(self, tmp_path):
        sd = SimulationData.from_snapshots(tmp_path)
        assert sd.snapshots == []
        assert sd.events_log == []
        assert sd.graph is None

    def test_empty_snapshots_preserves_graph(self, tmp_path):
        graph = MagicMock()
        sd = SimulationData.from_snapshots(tmp_path, graph=graph)
        assert sd.graph is graph

    def test_events_extracted(self, tmp_path):
        _write_snapshots(tmp_path, [
            {
                "round": 1,
                "changes": {
                    "events": [{"uid": "event_a"}],
                    "actions": [],
                    "meta_edges": [],
                    "migrations": [],
                },
                "summary": {"total": 10},
            },
            {
                "round": 2,
                "changes": {
                    "events": [{"uid": "event_b"}],
                    "actions": [{"actor": "x", "action": "flip"}],
                    "meta_edges": [{"source": "a", "target": "b"}],
                    "migrations": [{"entity": "e1", "from": "c0", "to": "c1"}],
                },
                "summary": {"total": 15},
            },
        ])
        sd = SimulationData.from_snapshots(tmp_path)
        assert len(sd.events_log) == 2
        assert sd.events_log[0]["round"] == 1
        assert sd.events_log[1]["round"] == 2
        assert len(sd.actions_log) == 1
        assert sd.actions_log[0]["round"] == 2
        assert len(sd.meta_edges_log) == 1
        assert len(sd.community_migrations) == 1

    def test_communities_initial_and_final(self, tmp_path):
        _write_snapshots(tmp_path, [
            {"round": 0, "changes": {}, "summary": {"clusters": 3}},
            {"round": 1, "changes": {}, "summary": {"clusters": 5}},
        ])
        sd = SimulationData.from_snapshots(tmp_path)
        assert sd.communities_initial == {"clusters": 3}
        assert sd.communities_final == {"clusters": 5}

    def test_missing_changes_key(self, tmp_path):
        """Snapshots without 'changes' key should not crash."""
        _write_snapshots(tmp_path, [
            {"round": 0, "summary": {}},
        ])
        sd = SimulationData.from_snapshots(tmp_path)
        assert sd.events_log == []
        assert sd.actions_log == []


# ── get_entity_timeline ──


class TestGetEntityTimeline:
    def test_empty_snapshots(self):
        sd = SimulationData()
        assert sd.get_entity_timeline("uid_1") == []

    def test_propagation_changes(self):
        sd = SimulationData(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "propagation": [
                            {
                                "target": "entity_a",
                                "source": "src",
                                "property": "stance",
                                "old": 0.0,
                                "new": 0.3,
                                "delta": 0.3,
                            },
                        ],
                        "actions": [],
                    },
                },
            ]
        )
        timeline = sd.get_entity_timeline("entity_a")
        assert len(timeline) == 1
        assert timeline[0]["source"] == "propagation"
        assert timeline[0]["property"] == "stance"
        assert timeline[0]["delta"] == 0.3

    def test_action_changes(self):
        sd = SimulationData(
            snapshots=[
                {
                    "round": 2,
                    "changes": {
                        "propagation": [],
                        "actions": [
                            {"actor": "entity_b", "action": "flip"},
                        ],
                    },
                },
            ]
        )
        timeline = sd.get_entity_timeline("entity_b")
        assert len(timeline) == 1
        assert timeline[0]["source"] == "action"
        assert timeline[0]["action"] == "flip"

    def test_ignores_other_entities(self):
        sd = SimulationData(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "propagation": [
                            {"target": "other", "property": "stance", "delta": 0.5},
                        ],
                        "actions": [
                            {"actor": "other", "action": "flip"},
                        ],
                    },
                },
            ]
        )
        assert sd.get_entity_timeline("entity_a") == []

    def test_multiple_rounds(self):
        sd = SimulationData(
            snapshots=[
                {
                    "round": 1,
                    "changes": {
                        "propagation": [
                            {"target": "e1", "property": "stance", "delta": 0.1},
                        ],
                        "actions": [],
                    },
                },
                {
                    "round": 2,
                    "changes": {
                        "propagation": [
                            {"target": "e1", "property": "volatility", "delta": 0.2},
                        ],
                        "actions": [
                            {"actor": "e1", "action": "ally"},
                        ],
                    },
                },
            ]
        )
        timeline = sd.get_entity_timeline("e1")
        assert len(timeline) == 3
        assert timeline[0]["round"] == 1
        assert timeline[1]["round"] == 2
        assert timeline[2]["round"] == 2


# ── get_stance_series ──


class TestGetStanceSeries:
    def test_empty_snapshots(self):
        sd = SimulationData()
        assert sd.get_stance_series("uid_1") == []

    def test_single_round_no_change(self):
        sd = SimulationData(
            snapshots=[{"round": 0, "changes": {"propagation": []}}]
        )
        series = sd.get_stance_series("uid_1")
        assert series == [0.0]

    def test_stance_updated(self):
        sd = SimulationData(
            snapshots=[
                {
                    "round": 0,
                    "changes": {
                        "propagation": [
                            {"target": "e1", "property": "stance", "new": 0.5},
                        ],
                    },
                },
                {
                    "round": 1,
                    "changes": {
                        "propagation": [
                            {"target": "e1", "property": "stance", "new": 0.8},
                        ],
                    },
                },
            ]
        )
        series = sd.get_stance_series("e1")
        assert series == [0.5, 0.8]

    def test_ignores_non_stance_properties(self):
        sd = SimulationData(
            snapshots=[
                {
                    "round": 0,
                    "changes": {
                        "propagation": [
                            {"target": "e1", "property": "volatility", "new": 0.9},
                        ],
                    },
                },
            ]
        )
        series = sd.get_stance_series("e1")
        assert series == [0.0]

    def test_retains_last_known_value(self):
        sd = SimulationData(
            snapshots=[
                {
                    "round": 0,
                    "changes": {
                        "propagation": [
                            {"target": "e1", "property": "stance", "new": 0.3},
                        ],
                    },
                },
                {
                    "round": 1,
                    "changes": {"propagation": []},
                },
            ]
        )
        series = sd.get_stance_series("e1")
        assert series == [0.3, 0.3]


# ── AnalysisSpace ABC ──


class _ConcreteSpace(AnalysisSpace):
    name = "test_space"

    def analyze(self) -> dict[str, Any]:
        return {"result": "ok", "count": len(self._data.snapshots)}


class TestAnalysisSpace:
    def test_concrete_subclass(self):
        sd = SimulationData(snapshots=[{"round": 0}])
        space = _ConcreteSpace(sd)
        result = space.analyze()
        assert result == {"result": "ok", "count": 1}

    def test_save_creates_json(self):
        sd = SimulationData(snapshots=[{"round": 0}])
        space = _ConcreteSpace(sd)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = space.save(tmpdir)
            assert path.name == "test_space.json"
            assert path.exists()
            with open(path) as f:
                data = json.load(f)
            assert data["result"] == "ok"

    def test_save_creates_parent_dirs(self):
        sd = SimulationData(snapshots=[])
        space = _ConcreteSpace(sd)
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = Path(tmpdir) / "a" / "b" / "c"
            path = space.save(nested)
            assert path.exists()

    def test_abstract_cannot_instantiate(self):
        with pytest.raises(TypeError):
            AnalysisSpace(SimulationData())
