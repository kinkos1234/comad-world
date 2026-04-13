"""Compatibility shim — canonical impl is in comad_eye.impact_analyzer
(ADR 0005, Tier 3 Phase 2). Existing callsites `from utils.impact_analyzer
import ImpactAnalyzer, ImpactReport` keep working while the codebase
migrates.
"""

from comad_eye.impact_analyzer import *  # noqa: F401,F403
from comad_eye.impact_analyzer import ImpactAnalyzer, ImpactReport  # noqa: F401

__all__ = ["ImpactAnalyzer", "ImpactReport"]
