"""Tests for task-specific LLM parameter resolution."""
from __future__ import annotations

import inspect

from comad_eye.config import LLMSettings, TaskLLMOverrides
from comad_eye.llm_client import LLMClient


class TestTaskOverrides:
    def test_default_overrides_exist(self):
        settings = LLMSettings()
        assert "extraction" in settings.task_overrides
        assert "interpretation" in settings.task_overrides
        assert "lens" in settings.task_overrides

    def test_extraction_low_temp(self):
        settings = LLMSettings()
        assert settings.task_overrides["extraction"].temperature == 0.1

    def test_interpretation_higher_temp(self):
        settings = LLMSettings()
        assert settings.task_overrides["interpretation"].temperature == 0.5

    def test_lens_larger_context(self):
        settings = LLMSettings()
        assert settings.task_overrides["lens"].num_ctx == 8192

    def test_custom_override(self):
        settings = LLMSettings(
            task_overrides={
                "custom": TaskLLMOverrides(temperature=0.9, max_tokens=256)
            }
        )
        assert settings.task_overrides["custom"].temperature == 0.9

    def test_override_none_fields_default_to_none(self):
        override = TaskLLMOverrides(temperature=0.1)
        assert override.max_tokens is None
        assert override.num_ctx is None

    def test_quote_override(self):
        settings = LLMSettings()
        assert settings.task_overrides["quote"].temperature == 0.6
        assert settings.task_overrides["quote"].max_tokens == 512

    def test_summarization_override(self):
        settings = LLMSettings()
        assert settings.task_overrides["summarization"].temperature == 0.3
        assert settings.task_overrides["summarization"].max_tokens == 512

    def test_extraction_max_tokens(self):
        settings = LLMSettings()
        assert settings.task_overrides["extraction"].max_tokens == 2048

    def test_lens_max_tokens(self):
        settings = LLMSettings()
        assert settings.task_overrides["lens"].max_tokens == 1024


class TestLLMClientTaskType:
    def test_task_type_parameter_accepted(self):
        """Verify generate() accepts task_type without error."""
        client = LLMClient(settings=LLMSettings())
        sig = inspect.signature(client.generate)
        assert "task_type" in sig.parameters

    def test_generate_json_task_type(self):
        sig = inspect.signature(LLMClient.generate_json)
        assert "task_type" in sig.parameters

    def test_task_type_defaults_to_none(self):
        """task_type defaults to None for backward compatibility."""
        client = LLMClient(settings=LLMSettings())
        sig = inspect.signature(client.generate)
        assert sig.parameters["task_type"].default is None

    def test_generate_json_task_type_defaults_to_none(self):
        sig = inspect.signature(LLMClient.generate_json)
        assert sig.parameters["task_type"].default is None
