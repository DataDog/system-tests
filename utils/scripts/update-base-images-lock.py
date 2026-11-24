#!/usr/bin/env python3
"""Thin wrapper: run utils/base_images/build_base_images.py with --update-lock."""

import subprocess
import sys
from pathlib import Path

_DIR = Path(__file__).resolve().parents[1]
_REAL = _DIR / "base_images" / "build_base_images.py"

result = subprocess.run([sys.executable, str(_REAL), "--update-lock"], check=False)

sys.exit(result.returncode)
