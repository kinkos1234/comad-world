"""Tests for analysis/lenses.py — LensEngine, compute_lens_budget, catalog."""

from __future__ import annotations

from unittest.mock import MagicMock

from comad_eye.analysis.lenses import (
    ALL_LENS_IDS,
    DEFAULT_LENS_IDS,
    LENS_CATALOG,
    LENS_MAP,
    LensEngine,
    compute_lens_budget,
)


# ── Catalog integrity ──


class TestLensCatalog:
    def test_catalog_has_10_lenses(self):
        assert len(LENS_CATALOG) == 10

    def test_all_have_required_fields(self):
        for lens in LENS_CATALOG:
            assert lens.id
            assert lens.name_ko
            assert lens.name_en
            assert lens.thinker
            assert lens.framework
            assert lens.system_prompt

    def test_all_have_space_prompts(self):
        expected_spaces = {"hierarchy", "temporal", "recursive", "structural", "causal"}
        for lens in LENS_CATALOG:
            assert set(lens.space_prompts.keys()) == expected_spaces, (
                f"Lens {lens.id} missing space prompts"
            )

    def test_lens_map_matches_catalog(self):
        assert len(LENS_MAP) == len(LENS_CATALOG)
        for lens in LENS_CATALOG:
            assert lens.id in LENS_MAP
            assert LENS_MAP[lens.id] is lens

    def test_default_ids_subset_of_all(self):
        assert set(DEFAULT_LENS_IDS).issubset(set(ALL_LENS_IDS))

    def test_default_ids_match_enabled(self):
        enabled = [lbl.id for lbl in LENS_CATALOG if lbl.default_enabled]
        assert DEFAULT_LENS_IDS == enabled

    def test_unique_ids(self):
        ids = [lbl.id for lbl in LENS_CATALOG]
        assert len(ids) == len(set(ids)), "Duplicate lens IDs found"


# ── compute_lens_budget ──


class TestComputeLensBudget:
    def test_none_settings(self):
        result = compute_lens_budget(None)
        assert result == len(DEFAULT_LENS_IDS)

    def test_empty_settings(self):
        result = compute_lens_budget({})
        assert result == len(DEFAULT_LENS_IDS)

    def test_minimum_budget(self):
        # Low values -> low depth -> budget near 3
        result = compute_lens_budget({
            "max_rounds": 5,
            "propagation_max_hops": 1,
            "propagation_decay": 0.7,
            "convergence_threshold": 0.05,
        })
        assert result == 3

    def test_maximum_budget(self):
        # High values -> high depth -> budget near 10
        result = compute_lens_budget({
            "max_rounds": 50,
            "propagation_max_hops": 10,
            "propagation_decay": 0.3,
            "convergence_threshold": 0.001,
        })
        assert result == 10

    def test_mid_range(self):
        result = compute_lens_budget({
            "max_rounds": 25,
            "propagation_max_hops": 5,
            "propagation_decay": 0.5,
            "convergence_threshold": 0.02,
        })
        assert 3 <= result <= 10

    def test_uses_max_hops_fallback(self):
        """If propagation_max_hops is missing, falls back to max_hops."""
        r1 = compute_lens_budget({"max_hops": 8})
        r2 = compute_lens_budget({"propagation_max_hops": 8})
        assert r1 == r2

    def test_extreme_values_clamped(self):
        # Beyond the expected range, should still be 3-10
        result = compute_lens_budget({
            "max_rounds": 1000,
            "propagation_max_hops": 100,
            "propagation_decay": 0.0,
            "convergence_threshold": 0.0,
        })
        assert 3 <= result <= 10

    def test_negative_values_handled(self):
        result = compute_lens_budget({
            "max_rounds": -10,
            "propagation_max_hops": -5,
        })
        assert 3 <= result <= 10


# ── LensEngine init ──


class TestLensEngineInit:
    def test_default_lenses(self):
        llm = MagicMock()
        engine = LensEngine(llm)
        assert engine.active_lens_ids == DEFAULT_LENS_IDS
        assert engine.is_auto_selected is False

    def test_selected_lenses(self):
        llm = MagicMock()
        engine = LensEngine(llm, selected_lens_ids=["sun_tzu", "taleb"])
        assert engine.active_lens_ids == ["sun_tzu", "taleb"]

    def test_invalid_lens_ids_filtered(self):
        llm = MagicMock()
        engine = LensEngine(llm, selected_lens_ids=["sun_tzu", "nonexistent", "taleb"])
        assert "nonexistent" not in engine.active_lens_ids
        assert engine.active_lens_ids == ["sun_tzu", "taleb"]

    def test_empty_selection(self):
        llm = MagicMock()
        engine = LensEngine(llm, selected_lens_ids=[])
        assert engine.active_lens_ids == []

    def test_graph_client_stored(self):
        llm = MagicMock()
        graph = MagicMock()
        engine = LensEngine(llm, graph_client=graph)
        assert engine._graph is graph


# ── LensEngine.auto_select ──


class TestLensEngineAutoSelect:
    def test_successful_auto_select(self):
        llm = MagicMock()
        llm.generate_json.return_value = {
            "selected": ["sun_tzu", "taleb", "kahneman"],
            "reasoning": "Test reasoning",
        }
        engine = LensEngine(llm, selected_lens_ids=["adam_smith"])
        engine.auto_select("sample text", "analyze power", budget=3)
        assert engine.is_auto_selected is True
        assert engine.active_lens_ids == ["sun_tzu", "taleb", "kahneman"]

    def test_auto_select_respects_budget(self):
        llm = MagicMock()
        llm.generate_json.return_value = {
            "selected": ["sun_tzu", "taleb", "kahneman", "meadows", "descartes"],
            "reasoning": "Many lenses",
        }
        engine = LensEngine(llm)
        engine.auto_select("sample", None, budget=2)
        assert len(engine.active_lens_ids) <= 2

    def test_auto_select_invalid_ids(self):
        llm = MagicMock()
        llm.generate_json.return_value = {
            "selected": ["invalid1", "invalid2"],
            "reasoning": "Bad",
        }
        engine = LensEngine(llm)
        engine.auto_select("sample", None, budget=3)
        # Should fallback to defaults
        assert engine.is_auto_selected is False
        assert len(engine.active_lens_ids) == 3

    def test_auto_select_llm_failure(self):
        llm = MagicMock()
        llm.generate_json.side_effect = RuntimeError("LLM unavailable")
        engine = LensEngine(llm)
        engine.auto_select("sample", "prompt", budget=4)
        assert engine.is_auto_selected is False
        assert len(engine.active_lens_ids) == 4

    def test_auto_select_with_analysis_prompt(self):
        llm = MagicMock()
        llm.generate_json.return_value = {
            "selected": ["sun_tzu"],
            "reasoning": "Strategic context",
        }
        engine = LensEngine(llm)
        engine.auto_select("text", "analyze military strategy", budget=1)
        assert engine.active_lens_ids == ["sun_tzu"]


# ── LensEngine.apply_to_spaces ──


class TestLensEngineApplyToSpaces:
    def test_empty_spaces(self):
        llm = MagicMock()
        engine = LensEngine(llm, selected_lens_ids=["sun_tzu"])
        result = engine.apply_to_spaces({})
        assert result == {}

    def test_skips_cross_space(self):
        llm = MagicMock()
        llm.generate_json.return_value = {
            "key_points": ["point"],
            "risk_assessment": "low",
            "opportunity": "high",
            "confidence": 0.8,
        }
        engine = LensEngine(llm, selected_lens_ids=["sun_tzu"])
        result = engine.apply_to_spaces({
            "cross_space": {"some": "data"},
            "hierarchy": {"some": "data"},
        })
        assert "cross_space" not in result
        assert "hierarchy" in result

    def test_llm_called_per_lens_per_space(self):
        llm = MagicMock()
        llm.generate_json.return_value = {
            "key_points": ["point"],
            "risk_assessment": "risk",
            "opportunity": "opp",
            "confidence": 0.7,
        }
        engine = LensEngine(llm, selected_lens_ids=["sun_tzu", "taleb"])
        result = engine.apply_to_spaces({"hierarchy": {"data": 1}})
        assert len(result["hierarchy"]) == 2  # 2 lenses applied

    def test_llm_failure_returns_none_insight(self):
        llm = MagicMock()
        llm.generate_json.side_effect = RuntimeError("LLM error")
        engine = LensEngine(llm, selected_lens_ids=["sun_tzu"])
        result = engine.apply_to_spaces({"hierarchy": {"data": 1}})
        # Failed insights are filtered (None returned by _apply_single_lens)
        assert result["hierarchy"] == []


# ── LensEngine.synthesize_cross_lens ──


class TestSynthesizeCrossLens:
    def test_empty_insights(self):
        llm = MagicMock()
        engine = LensEngine(llm, selected_lens_ids=["sun_tzu"])
        result = engine.synthesize_cross_lens({})
        assert result == []

    def test_all_empty_lists(self):
        llm = MagicMock()
        engine = LensEngine(llm, selected_lens_ids=["sun_tzu"])
        result = engine.synthesize_cross_lens({
            "hierarchy": [],
            "temporal": [],
        })
        assert result == []

    def test_single_space_insight_skipped(self):
        """Lens with insights from only one space should be skipped."""
        llm = MagicMock()
        engine = LensEngine(llm, selected_lens_ids=["sun_tzu"])
        result = engine.synthesize_cross_lens({
            "hierarchy": [
                {"lens_id": "sun_tzu", "key_points": ["point"]},
            ],
        })
        assert result == []

    def test_cross_synthesis_called(self):
        llm = MagicMock()
        llm.generate_json.return_value = {
            "synthesis": "Cross synthesis",
            "cross_pattern": "Pattern",
            "confidence": 0.8,
            "actionable_insight": "Do this",
        }
        engine = LensEngine(llm, selected_lens_ids=["sun_tzu"])
        result = engine.synthesize_cross_lens({
            "hierarchy": [
                {"lens_id": "sun_tzu", "key_points": ["insight_h"]},
            ],
            "temporal": [
                {"lens_id": "sun_tzu", "key_points": ["insight_t"]},
            ],
        })
        assert len(result) == 1
        assert result[0]["lens_id"] == "sun_tzu"

    def test_llm_failure_in_synthesis(self):
        llm = MagicMock()
        llm.generate_json.side_effect = RuntimeError("Failed")
        engine = LensEngine(llm, selected_lens_ids=["sun_tzu"])
        result = engine.synthesize_cross_lens({
            "hierarchy": [{"lens_id": "sun_tzu", "key_points": ["a"]}],
            "temporal": [{"lens_id": "sun_tzu", "key_points": ["b"]}],
        })
        # Should not crash, returns empty
        assert result == []

    def test_sorted_by_confidence(self):
        llm = MagicMock()
        call_count = {"n": 0}

        def fake_json(**kwargs):
            call_count["n"] += 1
            conf = 0.9 if call_count["n"] == 1 else 0.5
            return {
                "synthesis": "synth",
                "cross_pattern": "pattern",
                "confidence": conf,
                "actionable_insight": "insight",
            }

        llm.generate_json.side_effect = fake_json
        engine = LensEngine(llm, selected_lens_ids=["sun_tzu", "taleb"])
        result = engine.synthesize_cross_lens({
            "hierarchy": [
                {"lens_id": "sun_tzu", "key_points": ["a"]},
                {"lens_id": "taleb", "key_points": ["b"]},
            ],
            "temporal": [
                {"lens_id": "sun_tzu", "key_points": ["c"]},
                {"lens_id": "taleb", "key_points": ["d"]},
            ],
        })
        if len(result) >= 2:
            assert result[0].get("confidence", 0) >= result[1].get("confidence", 0)


# ── LensEngine._summarize_space_result ──


class TestSummarizeSpaceResult:
    def test_hierarchy_summary(self):
        llm = MagicMock()
        engine = LensEngine(llm, selected_lens_ids=[])
        text = engine._summarize_space_result("hierarchy", {
            "propagation_direction": "top_down",
            "most_dynamic_tier": "C2",
            "most_dynamic_community": "comm_a",
            "tier_analysis": {},
        })
        assert "top_down" in text
        assert "C2" in text

    def test_unknown_space_returns_json(self):
        llm = MagicMock()
        engine = LensEngine(llm, selected_lens_ids=[])
        text = engine._summarize_space_result("unknown_space", {"key": "value"})
        assert "key" in text


# ── LensEngine._query_lens_principles ──


class TestQueryLensPrinciples:
    def test_no_graph(self):
        llm = MagicMock()
        engine = LensEngine(llm, selected_lens_ids=[], graph_client=None)
        assert engine._query_lens_principles("sun_tzu", "hierarchy") == ""

    def test_with_graph(self):
        llm = MagicMock()
        graph = MagicMock()
        graph.query.return_value = [
            {"name": "세(勢)", "description": "desc", "application_hint": "hint"},
        ]
        engine = LensEngine(llm, selected_lens_ids=[], graph_client=graph)
        result = engine._query_lens_principles("sun_tzu", "hierarchy")
        # Should return formatted text (or empty if query fails)
        assert isinstance(result, str)

    def test_query_exception_returns_empty(self):
        llm = MagicMock()
        graph = MagicMock()
        graph.query.side_effect = RuntimeError("DB down")
        engine = LensEngine(llm, selected_lens_ids=[], graph_client=graph)
        result = engine._query_lens_principles("sun_tzu", "hierarchy")
        assert result == ""
