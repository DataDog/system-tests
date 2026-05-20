#!/bin/bash
#
# Print the contents of a log file inside a GitLab CI collapsible section.
#
# Usage:
#   ./scripts/ci/gitlab_docker_logs.sh <log_file> <section_name> <section_header>
#
#
# Reference: https://docs.gitlab.com/ci/jobs/job_logs/#custom-collapsible-sections

set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "ERROR: Missing required arguments." >&2
  echo "Usage: $0 <log_file> <section_name> <section_header>" >&2
  [[ -z "${1:-}" ]] && echo "ERROR: <log_file> is not set" >&2
  [[ -z "${2:-}" ]] && echo "ERROR: <section_name> is not set" >&2
  [[ -z "${3:-}" ]] && echo "ERROR: <section_header> is not set" >&2
  exit 1
fi

LOG_FILE="$1"
SECTION_NAME="$2"
SECTION_HEADER="$3"

section_start() {
  local section_title="${1}"
  local section_description="${2:-$section_title}"
  echo -e "\e[0Ksection_start:$(date +%s):${section_title}[collapsed=true]\r\e[0K${section_description}"
}

section_end() {
  local section_title="${1}"
  echo -e "\e[0Ksection_end:$(date +%s):${section_title}\r\e[0K"
}

section_start "${SECTION_NAME}" "${SECTION_HEADER}"

if [[ -f "${LOG_FILE}" ]]; then
  cat "${LOG_FILE}"
else
  echo "Log file not found: ${LOG_FILE}"
fi

section_end "${SECTION_NAME}"
