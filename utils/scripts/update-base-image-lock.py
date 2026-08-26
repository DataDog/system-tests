#!/usr/bin/env python3
"""Thin wrapper: run utils/base_image/build_base_images.py with --update-lock,
then regenerate the mirror images."""

import subprocess
import sys
from pathlib import Path

_DIR = Path(__file__).resolve().parents[1]
_REAL = _DIR / "base_image" / "build_base_images.py"

result = subprocess.run([sys.executable, str(_REAL), "--update-lock"])
print("\n=== You will need to run utils/scripts/update_mirror_images.py once the images are pushed to dockerhub ===")

sys.exit(result.returncode)
