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
#   AWS_CONSOLE_URL    S3 console URL printed in the banner when set.
#   DEBUG_LOGS_DOC_URL Documentation URL printed in the banner explaining how to
#                      interpret the logs (defaults to the AWS onboarding debug
#                      section). Set it per scenario type (k8s, docker-ssi, ...).

set -uo pipefail

# The collapsible-section helper lives next to this script.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COLLAPSIBLE_LOGS_SCRIPT="${SCRIPT_DIR}/gitlab_collapsible_logs.sh"

LABEL="${SCENARIO_SUFIX:-logs}"
DOC_URL="${DEBUG_LOGS_DOC_URL:-https://github.com/DataDog/system-tests/blob/main/docs/understand/scenarios/onboarding.md#how-to-debug-your-environment-and-tests-results}"

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

# 3. Final info banner with everything the user needs to navigate the log.
printf '\n%s\n  Logs for %s\n%s\n' \
  "================================================================================" \
  "${LABEL}" \
  "--------------------------------------------------------------------------------"
printf '  - Each log file above is wrapped in its own collapsible section.\n'
printf '    Click the triangle on the section header to expand/collapse it.\n'
printf '  - If some sections appear uncollapsed in this view, click\n'
printf '    "View full log" To view all collapsed sections (all logs)\n'
printf '  - You can always download the logs attached to the job\n'
if [ -n "${AWS_CONSOLE_URL:-}" ]; then
  printf '  - Full raw logs (including files >50MB stripped from the artifact)\n'
  printf '    are uploaded to S3:\n      %s\n' "${AWS_CONSOLE_URL}"
fi
printf '  - How to interpret these logs:\n      %s\n' \
  "${DOC_URL}"
printf '%s\n\n' \
  "================================================================================"
