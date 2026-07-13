#!/usr/bin/env bash
# Build the dd-trace-ruby conformance cdylib.
#   1. regenerate the rust suite crate from Temper
#   2. patch the start_span codegen bug (idempotent)
#   3. build the cdylib shim
# Run from anywhere; paths are resolved relative to the repo root.
set -euo pipefail
cd "$(dirname "$0")/../.."   # -> repo root (adapters/dd-trace-ruby/ -> ../..)

temper build -b rust
python3 adapters/dd-trace-ruby/patch_mod.py
( cd adapters/dd-trace-ruby/shim && cargo build )

echo "cdylib: $(ls adapters/dd-trace-ruby/shim/target/debug/libstr_ruby_shim.* 2>/dev/null | tr '\n' ' ')"
