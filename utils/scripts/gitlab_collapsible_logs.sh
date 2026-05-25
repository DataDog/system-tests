#!/bin/bash
#
# Print a log file inside a GitLab CI collapsible section.
#
# The file is emitted in full. GitLab's web UI only parses the last ~500 KiB
# of the trace, so for big jobs some sections will appear uncollapsed in the
# live view; the user can use "Show complete raw" to see every section folded
# correctly, or download the artifact from `reports/` for the original file.
#
# Usage:
#   ./gitlab_collapsible_logs.sh <log_file> <section_name> <section_header>
#
# Reference: https://docs.gitlab.com/ci/jobs/job_logs/#custom-collapsible-sections

set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <log_file> <section_name> <section_header>" >&2
  exit 1
fi

LOG_FILE="$1"
SECTION_NAME="$2"
SECTION_HEADER="$3"

ts=$(date +%s)

printf '\033[0Ksection_start:%d:%s[collapsed=true]\r\033[0K%s\n' \
  "${ts}" "${SECTION_NAME}" "${SECTION_HEADER}"

if [[ -f "${LOG_FILE}" ]]; then
  cat "${LOG_FILE}"
else
  echo "Log file not found: ${LOG_FILE}"
fi

printf '\033[0Ksection_end:%d:%s\r\033[0K\n' "${ts}" "${SECTION_NAME}"
