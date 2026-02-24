#!/usr/bin/env bash
# List flaky system tests for a tracer repo by querying failed GitHub Actions runs.
#
# Usage:
#   ./utils/scripts/list_flaky_system_tests.sh [REPO] [LIMIT]
#
# Examples:
#   ./utils/scripts/list_flaky_system_tests.sh                    # dd-trace-py, 50 runs
#   ./utils/scripts/list_flaky_system_tests.sh DataDog/dd-trace-py 100
#
# Output: FAILED test names, one per line, sorted by frequency (use with sort | uniq -c | sort -rn)
#
# See docs/CI/investigating-flaky-system-tests.md for methodology.

set -euo pipefail

REPO="${1:-DataDog/dd-trace-py}"
LIMIT="${2:-50}"
WORKFLOW="system-tests.yml"

echo "Fetching failed runs for $REPO (limit $LIMIT)..." >&2

for run_id in $(gh run list --repo "$REPO" --workflow "$WORKFLOW" --status failure --branch main --limit "$LIMIT" --json databaseId -q '.[].databaseId'); do
  for job_id in $(gh api "repos/$REPO/actions/runs/$run_id/jobs?per_page=100&filter=latest" \
    --jq '.jobs[] | select(.conclusion == "failure") | select(.name != "system-tests finished") | select(.name != "download-s3-wheels") | select(.name | test("build-wheels|system-tests-build") | not) | .id' 2>/dev/null); do
    gh api "repos/$REPO/actions/jobs/$job_id/logs" 2>/dev/null | \
      grep -oE 'FAILED [^ ]+::[^ ]+' | sed 's/^FAILED //' || true
    gh api "repos/$REPO/actions/jobs/$job_id/logs" 2>/dev/null | \
      grep -oE 'ERROR at setup of [^ ]+' | sed 's/^ERROR at setup of //' || true
  done
done | sort | uniq -c | sort -rn
