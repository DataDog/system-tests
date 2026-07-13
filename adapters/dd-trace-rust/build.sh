#!/usr/bin/env bash
# Build the dd-trace-rust conformance backend: (1) regenerate + patch the Temper
# rust suite crate this adapter path-deps (shared with ruby/php), (2) cargo build.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
bash "$REPO/adapters/dd-trace-ruby/build.sh" >/dev/null   # temper build -b rust + patch_mod.py (+ ruby cdylib)
( cd "$HERE" && cargo build --release )
