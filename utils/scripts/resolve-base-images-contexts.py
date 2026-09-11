#!/usr/bin/env python3
"""Thin wrapper: run utils/base_images/base_image.py directly."""

import os
import sys
from pathlib import Path

_REAL = Path(__file__).resolve().parents[1] / "base_images" / "base_image.py"
os.execv(sys.executable, [sys.executable, str(_REAL), *sys.argv[1:]])  # noqa: S606
