"""ADR 0002 PR 3 — eye/config/overrides.yaml merges over settings.yaml."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from comad_eye.config import _deep_merge, load_settings


def test_deep_merge_overwrites_leaves_and_preserves_siblings() -> None:
    base = {"a": {"x": 1, "y": 2}, "b": 3}
    overlay = {"a": {"y": 99, "z": 4}, "c": 5}
    merged = _deep_merge(dict(base), overlay)
    assert merged == {"a": {"x": 1, "y": 99, "z": 4}, "b": 3, "c": 5}


def test_load_settings_merges_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(textwrap.dedent("""
        neo4j:
          uri: "bolt://localhost:7687"
          user: "neo4j"
        llm:
          base_url: "http://localhost:11434/v1"
          model: "llama3.1:8b"
          temperature: 0.3
    """))
    overrides_path = tmp_path / "overrides.yaml"
    overrides_path.write_text(textwrap.dedent("""
        llm:
          model: "qwen3.5:9b"
    """))

    import utils.config as cfg
    monkeypatch.setattr(cfg, "_OVERRIDES_PATH", overrides_path)
    # Ensure env vars don't leak into this assertion.
    for env in ("LLM_MODEL", "NEO4J_URI"):
        monkeypatch.delenv(env, raising=False)

    settings = load_settings(settings_path)
    assert settings.llm.model == "qwen3.5:9b"
    assert settings.llm.temperature == 0.3  # preserved from base
    assert settings.neo4j.uri == "bolt://localhost:7687"


def test_load_settings_without_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text("neo4j:\n  uri: \"bolt://localhost:7687\"\n  user: \"neo4j\"\n")

    import utils.config as cfg
    monkeypatch.setattr(cfg, "_OVERRIDES_PATH", tmp_path / "missing.yaml")
    monkeypatch.delenv("NEO4J_URI", raising=False)

    settings = load_settings(settings_path)
    assert settings.neo4j.uri == "bolt://localhost:7687"
