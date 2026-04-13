"""Tests for analysis aggregator — error isolation and ranking logic."""

from __future__ import annotations

from unittest.mock import MagicMock

from comad_eye.analysis.aggregator import AnalysisAggregator
from comad_eye.analysis.base import SimulationData


def _empty_sim_data() -> SimulationData:
    """Create minimal SimulationData for testing."""
    data = MagicMock(spec=SimulationData)
    data.snapshots = [{"round": 0, "entities": []}, {"round": 1, "entities": []}]
    data.events_log = []
    data.actions_log = []
    data.meta_edges_log = []
    data.community_migrations = []
    return data


class TestRankFindings:
    def test_empty_spaces(self):
        """Empty analysis spaces should produce empty findings."""
        agg = AnalysisAggregator(_empty_sim_data(), "/tmp/test_analysis")
        findings = agg._rank_findings({}, {}, {}, {}, {}, {})
        assert findings == []

    def test_root_cause_ranking(self):
        causal = {
            "root_cause_ranking": [
                {"node": "entity_a", "downstream": 5, "total_impact": 0.8},
                {"node": "entity_b", "downstream": 3, "total_impact": 0.5},
            ]
        }
        agg = AnalysisAggregator(_empty_sim_data(), "/tmp/test_analysis")
        findings = agg._rank_findings({}, {}, {}, {}, causal, {})
        assert len(findings) >= 2
        # Should be sorted by confidence
        for i in range(len(findings) - 1):
            assert findings[i]["confidence"] >= findings[i + 1]["confidence"]

    def test_bridge_node_ranking(self):
        structural = {
            "bridge_nodes": [
                {"node": "bridge_a", "name": "Bridge A", "bridges": ["c1", "c2", "c3"]},
            ]
        }
        agg = AnalysisAggregator(_empty_sim_data(), "/tmp/test_analysis")
        findings = agg._rank_findings({}, {}, {}, structural, {}, {})
        assert len(findings) == 1
        assert "Bridge A" in findings[0]["finding"]

    def test_max_15_findings(self):
        """Should cap at 15 findings."""
        causal = {
            "root_cause_ranking": [
                {"node": f"e{i}", "downstream": 5, "total_impact": 0.8}
                for i in range(20)
            ]
        }
        agg = AnalysisAggregator(_empty_sim_data(), "/tmp/test_analysis")
        findings = agg._rank_findings({}, {}, {}, {}, causal, {})
        assert len(findings) <= 15


class TestSummaryHelpers:
    def test_summarize_hierarchy(self):
        agg = AnalysisAggregator(_empty_sim_data(), "/tmp/test_analysis")
        result = agg._summarize_hierarchy({"most_dynamic_tier": "C0", "most_dynamic_community": "C0_1"})
        assert "C0" in result
        assert "C0_1" in result

    def test_summarize_temporal(self):
        agg = AnalysisAggregator(_empty_sim_data(), "/tmp/test_analysis")
        result = agg._summarize_temporal({
            "leading_indicators": [{"leader": "A", "follower": "B"}],
            "event_reactions": {"e1": {}},
        })
        assert "1" in result  # 1 event reaction

    def test_summarize_causal(self):
        agg = AnalysisAggregator(_empty_sim_data(), "/tmp/test_analysis")
        result = agg._summarize_causal({
            "causal_dag": {"nodes": 10, "root_causes": ["a", "b"]},
        })
        assert "10" in result
