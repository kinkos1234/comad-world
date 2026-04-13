"""Tests for utils/config.py — settings loading and env override."""

from __future__ import annotations

import os

import pytest
import yaml

from comad_eye.config import (
    Settings,
    Neo4jSettings,
    LLMSettings,
    _apply_env_overrides,
    load_settings,
    load_yaml,
)


class TestSettingsDefaults:
    def test_default_neo4j(self):
        s = Neo4jSettings()
        assert s.uri == "bolt://localhost:7687"
        assert s.user == "neo4j"
        assert s.password == ""  # no hardcoded password
        assert s.database == "neo4j"

    def test_default_llm(self):
        s = LLMSettings()
        assert s.temperature == 0.3
        assert s.timeout == 120

    def test_settings_all_sections(self):
        s = Settings()
        assert hasattr(s, "neo4j")
        assert hasattr(s, "llm")
        assert hasattr(s, "ingestion")
        assert hasattr(s, "simulation")
        assert hasattr(s, "analysis")
        assert hasattr(s, "report")
        assert hasattr(s, "qa")
        assert hasattr(s, "logging")


class TestEnvOverrides:
    def test_override_string(self):
        raw = {"neo4j": {"uri": "bolt://old:7687"}}
        os.environ["NEO4J_URI"] = "bolt://new:7687"
        try:
            result = _apply_env_overrides(raw)
            assert result["neo4j"]["uri"] == "bolt://new:7687"
        finally:
            del os.environ["NEO4J_URI"]

    def test_override_float(self):
        raw = {"llm": {"temperature": 0.3}}
        os.environ["LLM_TEMPERATURE"] = "0.9"
        try:
            result = _apply_env_overrides(raw)
            assert result["llm"]["temperature"] == 0.9
        finally:
            del os.environ["LLM_TEMPERATURE"]

    def test_override_int(self):
        raw = {"llm": {"max_tokens": 1024}}
        os.environ["LLM_MAX_TOKENS"] = "8192"
        try:
            result = _apply_env_overrides(raw)
            assert result["llm"]["max_tokens"] == 8192
        finally:
            del os.environ["LLM_MAX_TOKENS"]

    def test_missing_env_no_override(self):
        raw = {"neo4j": {"uri": "bolt://original:7687"}}
        # Ensure env var is not set
        os.environ.pop("NEO4J_URI", None)
        result = _apply_env_overrides(raw)
        assert result["neo4j"]["uri"] == "bolt://original:7687"

    def test_creates_section_if_missing(self):
        raw = {}
        os.environ["NEO4J_PASSWORD"] = "secret"
        try:
            result = _apply_env_overrides(raw)
            assert result["neo4j"]["password"] == "secret"
        finally:
            del os.environ["NEO4J_PASSWORD"]


class TestLoadYaml:
    def test_loads_valid_yaml(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump({"key": "value"}))
        result = load_yaml(str(f))
        assert result == {"key": "value"}

    def test_empty_yaml_returns_dict(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text("")
        result = load_yaml(str(f))
        assert result == {}

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_yaml("/nonexistent/path.yaml")


class TestLoadSettings:
    def test_load_from_custom_path(self, tmp_path):
        f = tmp_path / "settings.yaml"
        f.write_text(yaml.dump({
            "neo4j": {"uri": "bolt://custom:7687"},
            "llm": {"model": "test-model"},
        }))
        s = load_settings(f)
        assert s.neo4j.uri == "bolt://custom:7687"
        assert s.llm.model == "test-model"

    def test_load_missing_file_uses_defaults(self, tmp_path):
        s = load_settings(tmp_path / "nonexistent.yaml")
        assert s.neo4j.uri == "bolt://localhost:7687"
