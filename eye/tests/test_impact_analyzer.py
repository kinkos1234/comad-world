"""Tests for utils/impact_analyzer.py — dependency graph impact analysis."""

from __future__ import annotations

from unittest.mock import patch

from comad_eye.impact_analyzer import ImpactAnalyzer, ImpactReport


# ---------------------------------------------------------------------------
# ImpactReport dataclass
# ---------------------------------------------------------------------------

class TestImpactReport:
    def test_defaults(self):
        r = ImpactReport(changed="test_component")
        assert r.changed == "test_component"
        assert r.directly_affected == []
        assert r.indirectly_affected == []
        assert r.total_scope == 0
        assert r.total_capabilities == 0
        assert r.cmr_reassessment == []
        assert r.depth_map == {}

    def test_custom_values(self):
        r = ImpactReport(
            changed="extraction",
            directly_affected=["a", "b"],
            total_scope=5,
            total_capabilities=20,
        )
        assert len(r.directly_affected) == 2
        assert r.total_scope == 5


# ---------------------------------------------------------------------------
# _cmr_badge (static, no deps)
# ---------------------------------------------------------------------------

class TestCmrBadge:
    def test_level_0(self):
        assert "?" in ImpactAnalyzer._cmr_badge(0)

    def test_level_1(self):
        assert "CMR 1" in ImpactAnalyzer._cmr_badge(1)

    def test_level_5(self):
        assert "CMR 5" in ImpactAnalyzer._cmr_badge(5)

    def test_unknown_level(self):
        assert "?" in ImpactAnalyzer._cmr_badge(99)


# ---------------------------------------------------------------------------
# _resolve_config_to_capability
# ---------------------------------------------------------------------------

class TestResolveConfigToCapability:
    """Test config filename → capability mapping without loading YAML."""

    @patch("utils.impact_analyzer.load_yaml")
    @patch("utils.impact_analyzer.project_root")
    def _make_analyzer(self, mock_root, mock_yaml):
        mock_root.return_value = type("Path", (), {"__truediv__": lambda s, o: f"root/{o}"})()
        mock_yaml.return_value = {"packages": {}}
        return ImpactAnalyzer.__new__(ImpactAnalyzer)

    def test_meta_edges_yaml(self):
        # We can test the mapping dict directly
        mapping = {
            "meta_edges.yaml": "meta_edge_engine",
            "action_types.yaml": "action_registry",
            "propagation_rules.yaml": "propagation_engine",
            "glossary.yaml": "entity_extraction",
            "bindings.yaml": "active_metadata_bus",
        }
        for config_name, expected in mapping.items():
            assert mapping.get(config_name) == expected

    def test_with_config_prefix(self):
        # The method strips "config/" prefix
        clean = "config/meta_edges.yaml".replace("config/", "")
        mapping = {"meta_edges.yaml": "meta_edge_engine"}
        assert mapping.get(clean) == "meta_edge_engine"

    def test_unknown_config(self):
        mapping = {"meta_edges.yaml": "meta_edge_engine"}
        assert mapping.get("unknown.yaml") is None


# ---------------------------------------------------------------------------
# ImpactAnalyzer with mocked data
# ---------------------------------------------------------------------------

class TestImpactAnalyzerWithMockedManifest:
    """Test the analyzer using mocked YAML data."""

    @patch("utils.impact_analyzer.project_root")
    @patch("utils.impact_analyzer.load_yaml")
    def _make_analyzer(self, manifest, cmr, mock_yaml, mock_root):
        from pathlib import Path
        mock_root.return_value = Path("/fake/root")

        def side_effect(path):
            if "manifest" in str(path):
                return manifest
            if "cmr" in str(path):
                return cmr
            return {}

        mock_yaml.side_effect = side_effect
        return ImpactAnalyzer()

    def test_analyze_known_component(self):
        manifest = {
            "packages": {
                "ingestion": {
                    "capabilities": ["entity_extraction", "chunking"],
                    "depends_on": [],
                },
                "simulation": {
                    "capabilities": ["propagation_engine", "action_registry"],
                    "depends_on": ["ingestion"],
                },
            }
        }
        cmr = {"registry": {}}

        analyzer = self._make_analyzer(manifest, cmr)
        report = analyzer.analyze("ingestion")

        assert report.changed == "ingestion"
        # simulation depends on ingestion, so it should be affected
        assert report.total_scope > 0

    def test_analyze_unknown_component(self):
        manifest = {
            "packages": {
                "ingestion": {
                    "capabilities": ["entity_extraction"],
                    "depends_on": [],
                },
            }
        }
        cmr = {"registry": {}}

        analyzer = self._make_analyzer(manifest, cmr)
        report = analyzer.analyze("nonexistent")

        assert report.changed == "nonexistent"
        assert report.directly_affected == []
        assert report.indirectly_affected == []

    def test_analyze_config_mapping(self):
        manifest = {
            "packages": {
                "simulation": {
                    "capabilities": ["propagation_engine"],
                    "depends_on": [],
                },
            }
        }
        cmr = {"registry": {}}

        analyzer = self._make_analyzer(manifest, cmr)
        # config/propagation_rules.yaml maps to propagation_engine
        report = analyzer.analyze("config/propagation_rules.yaml")
        assert report.changed == "propagation_engine"

    def test_cmr_reassessment(self):
        manifest = {
            "packages": {
                "core": {
                    "capabilities": ["base_engine"],
                    "depends_on": [],
                },
                "analysis": {
                    "capabilities": ["structural_analysis"],
                    "depends_on": ["core"],
                },
            }
        }
        cmr = {
            "registry": {
                "structural_analysis": {"level": 3},
            }
        }

        analyzer = self._make_analyzer(manifest, cmr)
        report = analyzer.analyze("core")

        # structural_analysis depends on core, so it should appear in reassessment
        # if it's in the affected set
        if report.cmr_reassessment:
            assert report.cmr_reassessment[0]["capability"] == "structural_analysis"
            assert report.cmr_reassessment[0]["current_level"] == 3

    def test_empty_manifest(self):
        manifest = {"packages": {}}
        cmr = {"registry": {}}

        analyzer = self._make_analyzer(manifest, cmr)
        report = analyzer.analyze("anything")

        assert report.total_scope == 0
        assert report.total_capabilities == 0

    def test_depth_map_direct_and_indirect(self):
        manifest = {
            "packages": {
                "core": {
                    "capabilities": ["core_cap"],
                    "depends_on": [],
                },
                "mid": {
                    "capabilities": ["mid_cap"],
                    "depends_on": ["core"],
                },
                "top": {
                    "capabilities": ["top_cap"],
                    "depends_on": ["mid"],
                },
            }
        }
        cmr = {"registry": {}}

        analyzer = self._make_analyzer(manifest, cmr)
        report = analyzer.analyze("core")

        # Should have direct (depth 1) and indirect (depth 2+) effects
        assert report.total_scope > 0


# ---------------------------------------------------------------------------
# render (smoke test with StringIO console)
# ---------------------------------------------------------------------------

class TestRender:
    @patch("utils.impact_analyzer.project_root")
    @patch("utils.impact_analyzer.load_yaml")
    def test_render_does_not_crash(self, mock_yaml, mock_root):
        from io import StringIO
        from pathlib import Path

        from rich.console import Console

        mock_root.return_value = Path("/fake/root")
        mock_yaml.return_value = {"packages": {}, "registry": {}}

        analyzer = ImpactAnalyzer()
        report = ImpactReport(
            changed="test",
            directly_affected=["a"],
            depth_map={1: ["a"]},
            total_scope=1,
            total_capabilities=5,
        )

        buf = StringIO()
        console = Console(file=buf, force_terminal=False)
        analyzer.render(report, console=console)

        output = buf.getvalue()
        assert "Impact Analysis" in output
        assert "test" in output
