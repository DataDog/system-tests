#!/bin/bash
#
# Render a job's logs at the END of a GitLab CI after_script:
#   1. Dump every file under reports/ as its own collapsible section.
#   2. Re-print the captured run.sh summary (when available).
#   3. Print a final banner explaining how to navigate the logs.
#
# Shared by the SSI / onboarding / k8s jobs so the logic lives in one place.
#
# Optional environment variables:
#   SCENARIO_SUFIX     Label shown in the section headers (defaults to "logs").
#   CI_PROJECT_DIR     GitLab built-in; used to locate run_output.log.
#   AWS_CONSOLE_URL    S3 console URL printed after the banner when set.

set -uo pipefail

# The collapsible-section helper lives next to this script.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COLLAPSIBLE_LOGS_SCRIPT="${SCRIPT_DIR}/gitlab_collapsible_logs.sh"

LABEL="${SCENARIO_SUFIX:-logs}"

# 1. Dump every log file as a collapsible section (full content).
if [ -f "${COLLAPSIBLE_LOGS_SCRIPT}" ]; then
  while IFS= read -r -d '' file; do
    section_id=$(printf '%s' "$file" | tr -c '[:alnum:]' '_')
    bash "${COLLAPSIBLE_LOGS_SCRIPT}" "$file" "logs_${LABEL}_${section_id}" "Logs for ${LABEL} - ${file}"
  done < <(find reports -type f \! -name report.json \! -name tests.log -print0)
else
  echo "Skipping collapsible log dump: ${COLLAPSIBLE_LOGS_SCRIPT} not found"
fi

# 2. Re-print the captured run.sh summary at the END.
if [ -n "${CI_PROJECT_DIR:-}" ] && [ -f "${CI_PROJECT_DIR}/run_output.log" ]; then
  printf '\n%s\n  Test run summary (captured from script: step)\n%s\n\n' \
    "================================================================================" \
    "================================================================================"
  tail -c 200000 "${CI_PROJECT_DIR}/run_output.log"
fi

# 3. Point at GitLab's full log. Collapsed sections only expand there.
printf '\nFor a better experience viewing these logs in GitLab, click "View full log".\n'
if [ -n "${AWS_CONSOLE_URL:-}" ]; then
  printf 'Logs on S3: %s\n' "${AWS_CONSOLE_URL}"
fi
printf '\n'
