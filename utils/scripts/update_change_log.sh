#!/usr/bin/env bash

(head -n 4 CHANGELOG.md
python utils/scripts/get-change-log.py "$@"
echo ""
tail -n +4 CHANGELOG.md) > new_CHANGELOG.md
mv new_CHANGELOG.md CHANGELOG.md
