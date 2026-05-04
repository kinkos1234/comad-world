#!/usr/bin/env python3
"""13 verify_final — re-measure l6_blocker_count after self-improve cycle.

Same logic as 05-verify-initial; supervisor compares the two for stopping
condition.
"""
from __future__ import annotations

import os
import sys
import pathlib

# Delegate to phase 05 (same logic, re-runs to capture post-improve state)
HERE = pathlib.Path(__file__).resolve().parent
phase05 = HERE / "05-verify-initial.py"
os.execv(sys.executable, [sys.executable, str(phase05)])
