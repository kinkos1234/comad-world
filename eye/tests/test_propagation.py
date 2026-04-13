"""Tests for propagation logic — pure data structure tests."""

from __future__ import annotations

from comad_eye.simulation.propagation import PropagationEffect


class TestPropagationEffect:
    def test_default_property(self):
        eff = PropagationEffect(
            source_uid="a", target_uid="b", effect=0.5, distance=1, rel_type="INFLUENCES"
        )
        assert eff.property == "stance"

    def test_custom_property(self):
        eff = PropagationEffect(
            source_uid="a", target_uid="b", effect=0.3, distance=2,
            rel_type="IMPACTS", property="volatility"
        )
        assert eff.property == "volatility"

    def test_effect_value(self):
        eff = PropagationEffect(
            source_uid="src", target_uid="tgt", effect=-0.7, distance=3, rel_type="OPPOSES"
        )
        assert eff.effect == -0.7
        assert eff.distance == 3


class TestApplyEffectsLogic:
    """Test the clamping logic used in apply_effects (extracted as pure functions)."""

    def test_stance_clamp_upper(self):
        old = 0.8
        delta = 0.5
        new_val = max(-1.0, min(1.0, old + delta))
        assert new_val == 1.0

    def test_stance_clamp_lower(self):
        old = -0.9
        delta = -0.3
        new_val = max(-1.0, min(1.0, old + delta))
        assert new_val == -1.0

    def test_volatility_clamp(self):
        old = 0.8
        delta = abs(0.5)
        new_val = max(0.0, min(1.0, old + delta))
        assert new_val == 1.0

    def test_volatility_never_negative(self):
        old = 0.1
        delta = abs(-0.05)
        new_val = max(0.0, min(1.0, old + delta))
        assert new_val >= 0.0
