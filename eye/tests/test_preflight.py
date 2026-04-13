"""Tests for utils/preflight.py — input pre-diagnosis."""

from __future__ import annotations

from comad_eye.preflight import PreflightResult, run_preflight


# ---------------------------------------------------------------------------
# PreflightResult dataclass
# ---------------------------------------------------------------------------

class TestPreflightResult:
    def test_all_fields(self):
        r = PreflightResult(
            chars=100,
            estimated_tokens=25,
            sentences=3,
            risk_level="low",
            recommended_batch_size=1,
            expected_batches=1,
            expected_llm_calls=1,
            warnings=[],
        )
        assert r.chars == 100
        assert r.risk_level == "low"
        assert r.warnings == []


# ---------------------------------------------------------------------------
# run_preflight — risk levels
# ---------------------------------------------------------------------------

class TestPreflightRiskLevels:
    def test_short_text_is_low_risk(self):
        text = "Hello world. This is a short text."
        result = run_preflight(text)
        assert result.risk_level == "low"
        assert result.warnings == []

    def test_medium_text_risk(self):
        # Generate ~5000-8000 tokens worth of text
        # tiktoken cl100k_base: roughly 4 chars per token for English
        text = "word " * 6000  # ~6000 tokens
        result = run_preflight(text)
        assert result.risk_level == "medium"

    def test_high_risk_text(self):
        # Generate >8000 tokens
        text = "word " * 10000  # ~10000 tokens
        result = run_preflight(text)
        assert result.risk_level == "high"
        assert len(result.warnings) >= 1

    def test_very_long_text_has_extra_warning(self):
        # >15000 tokens
        text = "word " * 20000
        result = run_preflight(text)
        assert result.risk_level == "high"
        assert len(result.warnings) >= 2


# ---------------------------------------------------------------------------
# Character and sentence counting
# ---------------------------------------------------------------------------

class TestCounting:
    def test_char_count(self):
        text = "Hello"
        result = run_preflight(text)
        assert result.chars == 5

    def test_sentence_count_periods(self):
        text = "First sentence. Second sentence. Third."
        result = run_preflight(text)
        assert result.sentences == 3

    def test_sentence_count_question_marks(self):
        text = "What? Why? How?"
        result = run_preflight(text)
        assert result.sentences == 3

    def test_sentence_count_exclamation(self):
        text = "Wow! Amazing!"
        result = run_preflight(text)
        assert result.sentences == 2

    def test_sentence_count_korean_period(self):
        text = "첫 번째 문장。두 번째 문장。"
        result = run_preflight(text)
        assert result.sentences == 2

    def test_minimum_one_sentence(self):
        text = "no punctuation here"
        result = run_preflight(text)
        assert result.sentences == 1

    def test_empty_string(self):
        result = run_preflight("")
        assert result.chars == 0
        assert result.estimated_tokens == 0
        assert result.sentences == 1  # min 1


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

class TestTokenEstimation:
    def test_token_count_is_positive_for_nonempty(self):
        result = run_preflight("Hello world")
        assert result.estimated_tokens > 0

    def test_empty_text_zero_tokens(self):
        result = run_preflight("")
        assert result.estimated_tokens == 0


# ---------------------------------------------------------------------------
# Batch calculation
# ---------------------------------------------------------------------------

class TestBatchCalculation:
    def test_single_batch_for_short_text(self):
        result = run_preflight("Short text.", batch_size=1)
        assert result.expected_batches >= 1

    def test_larger_batch_size_reduces_batches(self):
        text = "word " * 500
        result_1 = run_preflight(text, batch_size=1)
        result_4 = run_preflight(text, batch_size=4)
        assert result_4.expected_batches <= result_1.expected_batches

    def test_custom_chunk_parameters(self):
        text = "word " * 500
        result_small = run_preflight(text, chunk_size=100, chunk_overlap=20)
        result_large = run_preflight(text, chunk_size=500, chunk_overlap=50)
        assert result_small.expected_batches >= result_large.expected_batches


# ---------------------------------------------------------------------------
# LLM calls estimation
# ---------------------------------------------------------------------------

class TestLlmCallsEstimation:
    def test_low_risk_no_doubling(self):
        result = run_preflight("Short text.")
        assert result.expected_llm_calls == result.expected_batches

    def test_high_risk_doubles_calls(self):
        text = "word " * 10000
        result = run_preflight(text)
        assert result.risk_level == "high"
        # High risk doubles the call count
        assert result.expected_llm_calls == result.expected_batches * 2

    def test_recommended_batch_size_matches_input(self):
        result = run_preflight("text", batch_size=3)
        assert result.recommended_batch_size == 3
