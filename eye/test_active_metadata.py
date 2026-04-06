"""Tests for utils/active_metadata.py — event bus, change propagation."""

from __future__ import annotations

from unittest.mock import patch

from utils.active_metadata import ActiveMetadataBus, ChangeEvent, _count_by


# ---------------------------------------------------------------------------
# ChangeEvent dataclass
# ---------------------------------------------------------------------------

class TestChangeEvent:
    def test_defaults(self):
        evt = ChangeEvent(source="src", target="tgt")
        assert evt.source == "src"
        assert evt.target == "tgt"
        assert evt.property == ""
        assert evt.old_value is None
        assert evt.new_value is None
        assert evt.round == -1
        assert evt.event_type == "property_change"
        assert evt.timestamp  # auto-generated

    def test_custom_values(self):
        evt = ChangeEvent(
            source="entity_a",
            target="entity_b",
            property="stance",
            old_value=0.5,
            new_value=0.7,
            round=3,
            caused_by="propagation",
            event_type="cascade",
        )
        assert evt.property == "stance"
        assert evt.old_value == 0.5
        assert evt.new_value == 0.7
        assert evt.round == 3
        assert evt.event_type == "cascade"


# ---------------------------------------------------------------------------
# _count_by helper
# ---------------------------------------------------------------------------

class TestCountBy:
    def test_empty(self):
        assert _count_by([], lambda x: x) == {}

    def test_single_group(self):
        items = [1, 1, 1]
        result = _count_by(items, lambda x: "a")
        assert result == {"a": 3}

    def test_multiple_groups(self):
        items = ["a", "b", "a", "c", "b", "a"]
        result = _count_by(items, lambda x: x)
        assert result == {"a": 3, "b": 2, "c": 1}

    def test_with_objects(self):
        events = [
            ChangeEvent(source="s", target="t", event_type="property_change"),
            ChangeEvent(source="s", target="t", event_type="cascade"),
            ChangeEvent(source="s", target="t", event_type="property_change"),
        ]
        result = _count_by(events, lambda e: e.event_type)
        assert result == {"property_change": 2, "cascade": 1}


# ---------------------------------------------------------------------------
# ActiveMetadataBus basics
# ---------------------------------------------------------------------------

class TestActiveMetadataBusBasics:
    @patch("utils.active_metadata.project_root")
    @patch("utils.active_metadata.load_yaml")
    def _make_bus(self, mock_yaml, mock_root, bindings=None):
        from pathlib import Path
        mock_root.return_value = Path("/fake/root")
        mock_yaml.return_value = bindings or {}
        return ActiveMetadataBus()

    def test_initial_state(self):
        bus = self._make_bus()
        assert bus.change_log == []
        assert bus.invalidated == set()
        assert bus.stale_communities == set()

    def test_emit_adds_to_log(self):
        bus = self._make_bus()
        evt = ChangeEvent(source="a", target="b")
        bus.emit(evt)
        assert len(bus.change_log) == 1
        assert bus.change_log[0] is evt

    def test_emit_multiple_events(self):
        bus = self._make_bus()
        for i in range(5):
            bus.emit(ChangeEvent(source=f"s{i}", target=f"t{i}"))
        assert len(bus.change_log) == 5


# ---------------------------------------------------------------------------
# Subscribe and listener invocation
# ---------------------------------------------------------------------------

class TestSubscription:
    @patch("utils.active_metadata.project_root")
    @patch("utils.active_metadata.load_yaml")
    def _make_bus(self, mock_yaml=None, mock_root=None):
        from pathlib import Path
        mock_root.return_value = Path("/fake/root")
        mock_yaml.return_value = {}
        return ActiveMetadataBus()

    def test_listener_called_on_matching_event(self):
        bus = self._make_bus()
        received = []
        bus.subscribe("property_change", lambda evt: received.append(evt))

        evt = ChangeEvent(source="a", target="b", event_type="property_change")
        bus.emit(evt)

        assert len(received) == 1
        assert received[0] is evt

    def test_listener_not_called_for_different_type(self):
        bus = self._make_bus()
        received = []
        bus.subscribe("cascade", lambda evt: received.append(evt))

        evt = ChangeEvent(source="a", target="b", event_type="property_change")
        bus.emit(evt)

        assert len(received) == 0

    def test_multiple_listeners_same_type(self):
        bus = self._make_bus()
        counter_a = []
        counter_b = []
        bus.subscribe("property_change", lambda evt: counter_a.append(1))
        bus.subscribe("property_change", lambda evt: counter_b.append(1))

        bus.emit(ChangeEvent(source="a", target="b", event_type="property_change"))

        assert len(counter_a) == 1
        assert len(counter_b) == 1

    def test_listener_exception_does_not_crash(self):
        bus = self._make_bus()

        def bad_listener(evt):
            raise ValueError("intentional error")

        bus.subscribe("property_change", bad_listener)

        # Should not raise
        bus.emit(ChangeEvent(source="a", target="b", event_type="property_change"))
        assert len(bus.change_log) == 1


# ---------------------------------------------------------------------------
# emit_property_change
# ---------------------------------------------------------------------------

class TestEmitPropertyChange:
    @patch("utils.active_metadata.project_root")
    @patch("utils.active_metadata.load_yaml")
    def _make_bus(self, mock_yaml=None, mock_root=None):
        from pathlib import Path
        mock_root.return_value = Path("/fake/root")
        mock_yaml.return_value = {}
        return ActiveMetadataBus()

    def test_emits_correct_event(self):
        bus = self._make_bus()
        bus.emit_property_change(
            entity_uid="entity_1",
            prop="stance",
            old_val=0.3,
            new_val=0.7,
            round_num=2,
            caused_by="propagation",
        )

        assert len(bus.change_log) == 1
        evt = bus.change_log[0]
        assert evt.source == "entity_1"
        assert evt.target == "entity_1"
        assert evt.property == "stance"
        assert evt.old_value == 0.3
        assert evt.new_value == 0.7
        assert evt.round == 2
        assert evt.event_type == "property_change"


# ---------------------------------------------------------------------------
# Community stale marking
# ---------------------------------------------------------------------------

class TestCommunityStale:
    @patch("utils.active_metadata.project_root")
    @patch("utils.active_metadata.load_yaml")
    def _make_bus(self, mock_yaml=None, mock_root=None):
        from pathlib import Path
        mock_root.return_value = Path("/fake/root")
        mock_yaml.return_value = {}
        return ActiveMetadataBus()

    def test_mark_stale(self):
        bus = self._make_bus()
        bus.mark_community_stale("comm_1")
        assert "comm_1" in bus.stale_communities

    def test_mark_multiple_stale(self):
        bus = self._make_bus()
        bus.mark_community_stale("comm_1")
        bus.mark_community_stale("comm_2")
        assert len(bus.stale_communities) == 2

    def test_duplicate_marking(self):
        bus = self._make_bus()
        bus.mark_community_stale("comm_1")
        bus.mark_community_stale("comm_1")
        assert len(bus.stale_communities) == 1


# ---------------------------------------------------------------------------
# Invalidate analysis cache
# ---------------------------------------------------------------------------

class TestInvalidateAnalysisCache:
    @patch("utils.active_metadata.project_root")
    @patch("utils.active_metadata.load_yaml")
    def _make_bus(self, mock_yaml=None, mock_root=None):
        from pathlib import Path
        mock_root.return_value = Path("/fake/root")
        mock_yaml.return_value = {}
        return ActiveMetadataBus()

    def test_default_spaces(self):
        bus = self._make_bus()
        bus.invalidate_analysis_cache("entity_1")
        assert "structural:entity_1" in bus.invalidated
        assert "causal:entity_1" in bus.invalidated

    def test_custom_spaces(self):
        bus = self._make_bus()
        bus.invalidate_analysis_cache("entity_1", spaces=["temporal"])
        assert "temporal:entity_1" in bus.invalidated
        assert "structural:entity_1" not in bus.invalidated

    def test_multiple_invalidations(self):
        bus = self._make_bus()
        bus.invalidate_analysis_cache("e1")
        bus.invalidate_analysis_cache("e2")
        assert len(bus.invalidated) == 4  # 2 spaces * 2 entities


# ---------------------------------------------------------------------------
# Config change propagation
# ---------------------------------------------------------------------------

class TestConfigChangePropagation:
    @patch("utils.active_metadata.project_root")
    @patch("utils.active_metadata.load_yaml")
    def _make_bus(self, bindings, mock_yaml=None, mock_root=None):
        from pathlib import Path
        mock_root.return_value = Path("/fake/root")
        mock_yaml.return_value = bindings
        return ActiveMetadataBus()

    def test_config_change_triggers_propagation(self):
        bindings = {
            "change_propagation": [
                {
                    "when": "glossary.yaml changes",
                    "propagate_to": ["entity_extraction", "chunking"],
                    "active_metadata": {
                        "action": "invalidate_downstream",
                        "message": "Glossary changed",
                    },
                },
            ]
        }
        bus = self._make_bus(bindings)

        evt = ChangeEvent(
            source="glossary.yaml",
            target="config",
            event_type="config_change",
        )
        bus.emit(evt)

        # Should have cascade events + invalidation
        assert "entity_extraction" in bus.invalidated
        assert "chunking" in bus.invalidated
        # Original + 2 cascade events
        assert len(bus.change_log) == 3

    def test_config_change_notify_action(self):
        bindings = {
            "change_propagation": [
                {
                    "when": "settings.yaml changes",
                    "propagate_to": ["all_modules"],
                    "active_metadata": {
                        "action": "notify",
                        "message": "Settings updated",
                    },
                },
            ]
        }
        bus = self._make_bus(bindings)

        evt = ChangeEvent(
            source="settings.yaml",
            target="config",
            event_type="config_change",
        )
        bus.emit(evt)

        # Notify does not invalidate
        assert "all_modules" not in bus.invalidated
        # But cascade event is logged
        assert len(bus.change_log) == 2

    def test_no_matching_rule(self):
        bindings = {
            "change_propagation": [
                {
                    "when": "glossary.yaml changes",
                    "propagate_to": ["entity_extraction"],
                    "active_metadata": {"action": "invalidate_downstream"},
                },
            ]
        }
        bus = self._make_bus(bindings)

        evt = ChangeEvent(
            source="unrelated.yaml",
            target="config",
            event_type="config_change",
        )
        bus.emit(evt)

        assert len(bus.invalidated) == 0
        assert len(bus.change_log) == 1  # only original event


# ---------------------------------------------------------------------------
# Reset and get_summary
# ---------------------------------------------------------------------------

class TestResetAndSummary:
    @patch("utils.active_metadata.project_root")
    @patch("utils.active_metadata.load_yaml")
    def _make_bus(self, mock_yaml=None, mock_root=None):
        from pathlib import Path
        mock_root.return_value = Path("/fake/root")
        mock_yaml.return_value = {}
        return ActiveMetadataBus()

    def test_reset_clears_invalidated(self):
        bus = self._make_bus()
        bus.invalidate_analysis_cache("e1")
        assert len(bus.invalidated) > 0
        bus.reset()
        assert len(bus.invalidated) == 0

    def test_reset_does_not_clear_change_log(self):
        bus = self._make_bus()
        bus.emit(ChangeEvent(source="a", target="b"))
        bus.reset()
        assert len(bus.change_log) == 1

    def test_get_summary(self):
        bus = self._make_bus()
        bus.emit(ChangeEvent(source="a", target="b", event_type="property_change"))
        bus.emit(ChangeEvent(source="a", target="b", event_type="cascade"))
        bus.invalidate_analysis_cache("e1")
        bus.mark_community_stale("c1")

        summary = bus.get_summary()
        assert summary["total_events"] == 2
        assert summary["invalidated_count"] == 2
        assert summary["stale_communities"] == 1
        assert summary["event_types"]["property_change"] == 1
        assert summary["event_types"]["cascade"] == 1

    def test_get_summary_empty(self):
        bus = self._make_bus()
        summary = bus.get_summary()
        assert summary["total_events"] == 0
        assert summary["invalidated_count"] == 0
        assert summary["stale_communities"] == 0
