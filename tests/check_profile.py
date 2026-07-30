#!/usr/bin/env python3
"""Convenience entry point for the pytest static profile checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    raise SystemExit(
        subprocess.call(
            [sys.executable, "-m", "pytest", "-m", "not e2e and not installer"],
            cwd=ROOT,
        )
    )
