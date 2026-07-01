#!/usr/bin/env bash
set -euo pipefail
exec uv run --no-config --script \
    https://binaries.ddbuild.io/dd-repo-tools/default/ca/fb4f39a542e4dd42b646c300b539c7a9f4201531/mirror_images.py \
    "$@"
