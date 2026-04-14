"""Compatibility shim — canonical impl in comad_eye.narration.helpers (ADR 0005).

Aliases this module to the canonical one so BOTH public and private
names (_foo, __bar) resolve identically whether imported as
``comad_eye.narration.helpers`` or via the legacy path this file sits at.
"""
import sys as _sys
from comad_eye.narration.helpers import *  # noqa: F401,F403
import comad_eye.narration.helpers as _canonical
_sys.modules[__name__] = _canonical
