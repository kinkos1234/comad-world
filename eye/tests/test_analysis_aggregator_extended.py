"""Extended tests for analysis/aggregator.py — run_all, _aggregate, _save_result."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from comad_eye.analysis.aggregator import AnalysisAggregator
from comad_eye.analysis.base import SimulationData


def _empty_sim_data() -> SimulationData:
    data = MagicMock(spec=SimulationData)
    data.snapshots = [{"round": 0}, {"round": 1}]
    data.events_log = [{"uid": "e1"}]
    data.actions_log = []
    data.meta_edges_log = []
    data.community_migrations = []
    return data


class TestAggregatorInit:
    def test_creates_output_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "new_dir"
            AnalysisAggregator(_empty_sim_data(), out)
            assert out.exists()

    def test_stores_parameters(self):
        sd = _empty_sim_data()
        llm = MagicMock()
        agg = AnalysisAggregator(
            sd,
            "/tmp/test",
            llm=llm,
            selected_lenses=["sun_tzu"],
            seed_text="test seed",
            parallel=False,
        )
        assert agg._llm is llm
        assert agg._selected_lenses == ["sun_tzu"]
        assert agg._seed_text == "test seed"
        assert agg._parallel is False


class TestSaveResult:
    def test_save_creates_json_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agg = AnalysisAggregator(_empty_sim_data(), tmpdir)
            path = agg._save_result("test_output", {"key": "value"})
            assert path.exists()
            assert path.name == "test_output.json"
            with open(path) as f:
                data = json.load(f)
            assert data["key"] == "value"

    def test_save_handles_non_serializable(self):
        """default=str should handle non-JSON types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agg = AnalysisAggregator(_empty_sim_data(), tmpdir)
            path = agg._save_result("special", {"path": Path("/tmp")})
            assert path.exists()


class TestAggregate:
    def _make_agg(self) -> AnalysisAggregator:
        return AnalysisAggregator(_empty_sim_data(), "/tmp/test_analysis")

    def test_aggregate_all_empty(self):
        agg = self._make_agg()
        result = agg._aggregate(
            hierarchy={},
            temporal={},
            recursive={},
            structural={},
            causal={},
            cross={},
        )
        assert "simulation_summary" in result
        assert "key_findings" in result
        assert "spaces" in result
        assert result["simulation_summary"]["total_rounds"] == 2
        assert result["simulation_summary"]["total_events"] == 1

    def test_aggregate_includes_lens_insights(self):
        agg = self._make_agg()
        result = agg._aggregate(
            hierarchy={},
            temporal={},
            recursive={},
            structural={},
            causal={},
            cross={},
            lens_insights={
                "hierarchy": [
                    {
                        "lens_name": "손자",
                        "thinker": "손자 (孫子)",
                        "key_points": ["point1"],
                        "risk_assessment": "low",
                        "opportunity": "high",
                        "confidence": 0.8,
                    },
                ],
            },
        )
        assert "lens_insights" in result

    def test_aggregate_without_lens_insights(self):
        agg = self._make_agg()
        result = agg._aggregate(
            hierarchy={},
            temporal={},
            recursive={},
            structural={},
            causal={},
            cross={},
        )
        assert "lens_insights" not in result

    def test_aggregate_includes_cross_lens(self):
        agg = self._make_agg()
        result = agg._aggregate(
            hierarchy={},
            temporal={},
            recursive={},
            structural={},
            causal={},
            cross={},
            cross_lens_insights=[{"synthesis": "test"}],
        )
        assert "lens_cross_insights" in result

    def test_spaces_summary_structure(self):
        agg = self._make_agg()
        result = agg._aggregate(
            hierarchy={"most_dynamic_tier": "C1", "most_dynamic_community": "c_a"},
            temporal={"leading_indicators": [], "event_reactions": {}},
            recursive={"loop_summary": {"positive_count": 1, "negative_count": 2}},
            structural={"bridge_nodes": [{"node": "b1"}], "structural_holes": []},
            causal={"causal_dag": {"nodes": 5, "root_causes": ["r1"]}, "root_cause_ranking": []},
            cross={"insight_count": 3, "meta_pattern_count": 1},
        )
        spaces = result["spaces"]
        assert "hierarchy" in spaces
        assert "temporal" in spaces
        assert "recursive" in spaces
        assert "structural" in spaces
        assert "causal" in spaces
        assert "cross_space" in spaces


class TestRankFindingsExtended:
    def _make_agg(self) -> AnalysisAggregator:
        return AnalysisAggregator(_empty_sim_data(), "/tmp/test_analysis")

    def test_meta_patterns_included(self):
        cross = {
            "meta_patterns": [
                {
                    "description": "Meta pattern found",
                    "spaces": ["structural", "causal"],
                    "leverage_score": 0.9,
                },
            ],
        }
        agg = self._make_agg()
        findings = agg._rank_findings({}, {}, {}, {}, {}, cross)
        assert len(findings) == 1
        assert "Meta pattern" in findings[0]["finding"]

    def test_positive_feedback_loop(self):
        recursive = {
            "feedback_loops": [
                {"type": "positive", "nodes": ["A", "B", "C"], "strength": 0.5},
            ],
        }
        agg = self._make_agg()
        findings = agg._rank_findings({}, {}, recursive, {}, {}, {})
        assert any("양의 피드백" in f["finding"] for f in findings)

    def test_leading_indicators(self):
        temporal = {
            "leading_indicators": [
                {
                    "leader_name": "Leader",
                    "follower_name": "Follower",
                    "correlation": 0.85,
                    "lag_rounds": 2,
                },
            ],
        }
        agg = self._make_agg()
        findings = agg._rank_findings({}, temporal, {}, {}, {}, {})
        assert any("Leader" in f["finding"] for f in findings)

    def test_confidence_sorting(self):
        causal = {
            "root_cause_ranking": [
                {"node": "e1", "downstream": 10, "total_impact": 0.1},
            ],
        }
        temporal = {
            "leading_indicators": [
                {"leader_name": "L", "follower_name": "F", "correlation": 0.99, "lag_rounds": 1},
            ],
        }
        agg = self._make_agg()
        findings = agg._rank_findings({}, temporal, {}, {}, causal, {})
        for i in range(len(findings) - 1):
            assert findings[i]["confidence"] >= findings[i + 1]["confidence"]

    def test_rank_numbers_are_sequential(self):
        causal = {
            "root_cause_ranking": [
                {"node": f"e{i}", "downstream": 5, "total_impact": 0.5}
                for i in range(5)
            ],
        }
        agg = self._make_agg()
        findings = agg._rank_findings({}, {}, {}, {}, causal, {})
        for i, f in enumerate(findings):
            assert f["rank"] == i + 1

    def test_confidence_capped(self):
        """Root cause confidence should be capped at 0.95."""
        causal = {
            "root_cause_ranking": [
                {"node": "big", "downstream": 100, "total_impact": 10.0},
            ],
        }
        agg = self._make_agg()
        findings = agg._rank_findings({}, {}, {}, {}, causal, {})
        assert findings[0]["confidence"] <= 0.95


class TestRunAll:
    @patch("comad_eye.analysis.aggregator.CrossSpace")
    @patch("comad_eye.analysis.aggregator.CausalSpace")
    @patch("comad_eye.analysis.aggregator.StructuralSpace")
    @patch("comad_eye.analysis.aggregator.RecursiveSpace")
    @patch("comad_eye.analysis.aggregator.TemporalSpace")
    @patch("comad_eye.analysis.aggregator.HierarchySpace")
    def test_run_all_sequential(
        self, MockH, MockT, MockR, MockS, MockC, MockX
    ):
        """Test sequential (non-parallel) execution."""
        names = ["hierarchy", "temporal", "recursive", "structural", "causal"]
        for MockSpace, n in zip([MockH, MockT, MockR, MockS, MockC], names):
            instance = MockSpace.return_value
            instance.analyze.return_value = {}
            instance.name = n
        MockX.return_value.analyze.return_value = {
            "cross_insights": [],
            "meta_patterns": [],
            "insight_count": 0,
            "meta_pattern_count": 0,
        }
        MockX.return_value.name = "cross_space"

        with tempfile.TemporaryDirectory() as tmpdir:
            agg = AnalysisAggregator(
                _empty_sim_data(), tmpdir, parallel=False
            )
            result = agg.run_all()
            assert "simulation_summary" in result
            assert "key_findings" in result
            assert "spaces" in result

    @patch("comad_eye.analysis.aggregator.CrossSpace")
    @patch("comad_eye.analysis.aggregator.CausalSpace")
    @patch("comad_eye.analysis.aggregator.StructuralSpace")
    @patch("comad_eye.analysis.aggregator.RecursiveSpace")
    @patch("comad_eye.analysis.aggregator.TemporalSpace")
    @patch("comad_eye.analysis.aggregator.HierarchySpace")
    def test_space_failure_isolated(
        self, MockH, MockT, MockR, MockS, MockC, MockX
    ):
        """A failing space should not crash the aggregator."""
        MockH.return_value.analyze.side_effect = RuntimeError("Boom")
        MockH.return_value.name = "hierarchy"

        for MockSpace, name in [
            (MockT, "temporal"), (MockR, "recursive"),
            (MockS, "structural"), (MockC, "causal"),
        ]:
            MockSpace.return_value.analyze.return_value = {}
            MockSpace.return_value.name = name

        MockX.return_value.analyze.return_value = {
            "cross_insights": [],
            "meta_patterns": [],
            "insight_count": 0,
            "meta_pattern_count": 0,
        }
        MockX.return_value.name = "cross_space"

        with tempfile.TemporaryDirectory() as tmpdir:
            agg = AnalysisAggregator(
                _empty_sim_data(), tmpdir, parallel=False
            )
            result = agg.run_all()
            # hierarchy should be empty dict due to error isolation
            assert result is not None
