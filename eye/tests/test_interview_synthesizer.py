"""Tests for narration/interview_synthesizer.py — 0% → target 100%"""

from __future__ import annotations

from unittest.mock import MagicMock

from comad_eye.narration.interview_synthesizer import InterviewSynthesizer


def _make_synth(entities=None, neighbors=None):
    client = MagicMock()
    client.get_entity.side_effect = lambda uid: (entities or {}).get(uid)
    client.get_neighbors.side_effect = lambda uid, **kw: (neighbors or {}).get(uid, [])
    return InterviewSynthesizer(client)


# ── _determine_tone ──

class TestDetermineTone:
    def test_positive(self):
        assert InterviewSynthesizer._determine_tone({"stance": 0.5}) == "긍정적/낙관적"

    def test_negative(self):
        assert InterviewSynthesizer._determine_tone({"stance": -0.5}) == "부정적/비관적"

    def test_neutral(self):
        assert InterviewSynthesizer._determine_tone({"stance": 0.0}) == "중립적/분석적"

    def test_boundary_positive(self):
        assert InterviewSynthesizer._determine_tone({"stance": 0.3}) == "중립적/분석적"

    def test_boundary_negative(self):
        assert InterviewSynthesizer._determine_tone({"stance": -0.3}) == "중립적/분석적"

    def test_missing_stance(self):
        assert InterviewSynthesizer._determine_tone({}) == "중립적/분석적"


# ── _determine_intensity ──

class TestDetermineIntensity:
    def test_high(self):
        assert InterviewSynthesizer._determine_intensity({"influence_score": 0.8}) == "단정적/선언적"

    def test_medium(self):
        assert InterviewSynthesizer._determine_intensity({"influence_score": 0.5}) == "확신적/분석적"

    def test_low(self):
        assert InterviewSynthesizer._determine_intensity({"influence_score": 0.2}) == "관찰적/조심스러운"

    def test_missing(self):
        assert InterviewSynthesizer._determine_intensity({}) == "관찰적/조심스러운"


# ── build_interview_context ──

class TestBuildInterviewContext:
    def test_empty_uids(self):
        synth = _make_synth()
        assert synth.build_interview_context([]) == []

    def test_missing_entity_skipped(self):
        synth = _make_synth(entities={})
        result = synth.build_interview_context(["nonexistent"])
        assert result == []

    def test_basic_context(self):
        entities = {
            "e1": {
                "name": "Alpha",
                "object_type": "Technology",
                "stance": 0.5,
                "volatility": 0.2,
                "influence_score": 0.8,
                "community_id": "c1",
            }
        }
        neighbors = {
            "e1": [
                {"name": "Beta", "rel_type": "USES", "weight": 0.9},
            ]
        }
        synth = _make_synth(entities, neighbors)
        result = synth.build_interview_context(["e1"])

        assert len(result) == 1
        ctx = result[0]
        assert ctx["name"] == "Alpha"
        assert ctx["object_type"] == "Technology"
        assert ctx["stance"] == 0.5
        assert ctx["tone"] == "긍정적/낙관적"
        assert ctx["intensity"] == "단정적/선언적"
        assert len(ctx["key_relationships"]) == 1
        assert ctx["key_relationships"][0]["target"] == "Beta"

    def test_actions_filtered_by_actor(self):
        entities = {"e1": {"name": "A", "stance": 0, "volatility": 0, "influence_score": 0}}
        synth = _make_synth(entities)
        actions = [
            {"actor": "e1", "action": "act1"},
            {"actor": "e2", "action": "act2"},
            {"actor": "e1", "action": "act3"},
        ]
        result = synth.build_interview_context(["e1"], actions_log=actions)
        assert result[0]["action_history"] == ["act1", "act3"]

    def test_actions_capped_at_5(self):
        entities = {"e1": {"name": "A", "stance": 0, "volatility": 0, "influence_score": 0}}
        synth = _make_synth(entities)
        actions = [{"actor": "e1", "action": f"act{i}"} for i in range(10)]
        result = synth.build_interview_context(["e1"], actions_log=actions)
        assert len(result[0]["action_history"]) == 5

    def test_relationships_capped_at_5(self):
        entities = {"e1": {"name": "A", "stance": 0, "volatility": 0, "influence_score": 0}}
        neighbors = {"e1": [{"name": f"N{i}", "rel_type": "R", "weight": 1.0} for i in range(10)]}
        synth = _make_synth(entities, neighbors)
        result = synth.build_interview_context(["e1"])
        assert len(result[0]["key_relationships"]) == 5

    def test_no_actions_log(self):
        entities = {"e1": {"name": "A", "stance": 0, "volatility": 0, "influence_score": 0}}
        synth = _make_synth(entities)
        result = synth.build_interview_context(["e1"], actions_log=None)
        assert result[0]["action_history"] == []

    def test_defaults_for_missing_fields(self):
        # Entity dict must be truthy (non-empty) to not be skipped
        entities = {"e1": {"uid": "e1"}}
        neighbors = {"e1": []}
        synth = _make_synth(entities, neighbors)
        result = synth.build_interview_context(["e1"])
        ctx = result[0]
        assert ctx["name"] == "e1"  # falls back to uid
        assert ctx["object_type"] == "Entity"
        assert ctx["stance"] == 0.0


# ── generate_interview_prompt ──

class TestGenerateInterviewPrompt:
    def test_basic_prompt(self):
        ctx = {
            "name": "Alpha",
            "object_type": "Technology",
            "stance": 0.5,
            "tone": "긍정적/낙관적",
            "intensity": "단정적/선언적",
            "influence_score": 0.8,
            "key_relationships": [
                {"relation": "USES", "target": "Beta"},
            ],
            "action_history": ["act1"],
        }
        synth = _make_synth()
        prompt = synth.generate_interview_prompt(ctx)
        assert "Alpha" in prompt
        assert "Technology" in prompt
        assert "USES→Beta" in prompt
        assert "act1" in prompt

    def test_empty_relationships_and_actions(self):
        ctx = {
            "name": "A",
            "object_type": "Entity",
            "stance": 0.0,
            "tone": "중립적/분석적",
            "intensity": "관찰적/조심스러운",
            "influence_score": 0.0,
            "key_relationships": [],
            "action_history": [],
        }
        synth = _make_synth()
        prompt = synth.generate_interview_prompt(ctx)
        assert "없음" in prompt

    def test_caps_relationships_at_3(self):
        ctx = {
            "name": "A",
            "object_type": "E",
            "stance": 0,
            "tone": "t",
            "intensity": "i",
            "influence_score": 0,
            "key_relationships": [{"relation": f"R{i}", "target": f"T{i}"} for i in range(5)],
            "action_history": [],
        }
        synth = _make_synth()
        prompt = synth.generate_interview_prompt(ctx)
        # Only 3 relationships shown
        assert "R3" not in prompt


# ── validate_quote ──

class TestValidateQuote:
    def test_positive_entity_with_negative_quote(self):
        synth = _make_synth()
        ctx = {"stance": 0.5, "tone": "긍정적/낙관적"}
        assert synth.validate_quote("하락과 위험이 예상됩니다", ctx) is False

    def test_negative_entity_with_positive_quote(self):
        synth = _make_synth()
        ctx = {"stance": -0.5, "tone": "부정적/비관적"}
        assert synth.validate_quote("성장과 기회가 있습니다", ctx) is False

    def test_positive_entity_with_positive_quote(self):
        synth = _make_synth()
        ctx = {"stance": 0.5, "tone": "긍정적/낙관적"}
        assert synth.validate_quote("성장이 기대됩니다", ctx) is True

    def test_neutral_entity_any_quote(self):
        synth = _make_synth()
        ctx = {"stance": 0.0, "tone": "중립적/분석적"}
        assert synth.validate_quote("하락이 우려됩니다", ctx) is True

    def test_mixed_words_allowed(self):
        synth = _make_synth()
        ctx = {"stance": 0.5, "tone": "긍정적/낙관적"}
        # Both positive and negative — allowed
        assert synth.validate_quote("성장과 위험이 공존합니다", ctx) is True

    def test_no_sentiment_words(self):
        synth = _make_synth()
        ctx = {"stance": 0.5, "tone": "긍정적/낙관적"}
        assert synth.validate_quote("기술적 분석입니다", ctx) is True
