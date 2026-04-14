"""pytest setup for eye.

Adds `src/` to sys.path so tests can `import comad_eye` during the Tier 3
Phase 2 migration. The legacy flat layout (`from utils.X`,
`from analysis.X`, etc.) still works — the legacy modules are at
eye/ cwd which pytest already picks up.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SRC = _HERE / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
# eye/ itself hosts api/, app/, routes/, tests/ etc. — entry-point dirs
# that tests import directly. Keep them on sys.path during migration.
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


# Eager-import commonly-patched submodules so @patch("comad_eye.X.sub.Y")
# resolves via getattr without each test file having to preload (ADR 0005).
# Wrap in try/except because several submodules pull heavy optional deps
# (kss, igraph, torch) that aren't guaranteed in every test environment.
def _eager_import_submodules() -> None:
    import importlib
    targets = [
        "comad_eye.simulation.engine",
        "comad_eye.simulation.propagation",
        "comad_eye.simulation.action_resolver",
        "comad_eye.simulation.event_chain",
        "comad_eye.simulation.snapshot",
        "comad_eye.simulation.prediction_tracker",
        "comad_eye.analysis.aggregator",
        "comad_eye.analysis.base",
        "comad_eye.pipeline.orchestrator",
        "comad_eye.narration.report_generator",
        "comad_eye.narration.narrative_builder",
        "comad_eye.narration.interview_synthesizer",
        "comad_eye.narration.qa_session",
        "comad_eye.narration.helpers",
        "comad_eye.graph.loader",
        "comad_eye.graph.summarizer",
        "comad_eye.graph.neo4j_client",
        "comad_eye.ontology.schema",
        "comad_eye.ontology.action_registry",
        "comad_eye.ontology.meta_edge_engine",
    ]
    for t in targets:
        try:
            importlib.import_module(t)
        except ImportError:
            pass


_eager_import_submodules()
