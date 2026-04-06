"""Tests for LLM client — JSON extraction and pure functions."""

from __future__ import annotations

from utils.llm_client import LLMClient


class TestExtractJsonFromText:
    """Test _extract_json_from_text static method."""

    def test_valid_json_object(self):
        text = '{"key": "value"}'
        assert LLMClient._extract_json_from_text(text) == text

    def test_valid_json_array(self):
        text = '[1, 2, 3]'
        assert LLMClient._extract_json_from_text(text) == text

    def test_json_in_code_block(self):
        text = 'Here is the result:\n```json\n{"entities": ["a", "b"]}\n```\nDone.'
        result = LLMClient._extract_json_from_text(text)
        assert result == '{"entities": ["a", "b"]}'

    def test_json_in_bare_code_block(self):
        text = '```\n{"key": 1}\n```'
        result = LLMClient._extract_json_from_text(text)
        assert result == '{"key": 1}'

    def test_json_embedded_in_text(self):
        text = 'The analysis shows that {"result": "positive"} is the conclusion.'
        result = LLMClient._extract_json_from_text(text)
        assert result == '{"result": "positive"}'

    def test_array_embedded_in_text(self):
        text = 'Found entities: [{"name": "A"}, {"name": "B"}] in the text.'
        result = LLMClient._extract_json_from_text(text)
        assert result == '[{"name": "A"}, {"name": "B"}]'

    def test_no_json_returns_original(self):
        text = 'No JSON here, just plain text.'
        result = LLMClient._extract_json_from_text(text)
        assert result == text

    def test_whitespace_handling(self):
        text = '  \n  {"key": "value"}  \n  '
        result = LLMClient._extract_json_from_text(text)
        assert result == '{"key": "value"}'

    def test_thinking_model_output(self):
        """qwen3 thinking model wraps JSON in explanation."""
        text = (
            "<think>Let me analyze this carefully...</think>\n\n"
            "Based on my analysis, here are the entities:\n"
            '```json\n{"entities": [{"name": "Korea", "type": "Actor"}]}\n```\n'
            "These entities represent the key actors."
        )
        result = LLMClient._extract_json_from_text(text)
        assert '"Korea"' in result
        assert '"Actor"' in result

    def test_nested_json(self):
        text = '{"outer": {"inner": [1, 2, 3]}}'
        result = LLMClient._extract_json_from_text(text)
        assert result == text
