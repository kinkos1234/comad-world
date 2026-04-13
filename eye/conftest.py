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
