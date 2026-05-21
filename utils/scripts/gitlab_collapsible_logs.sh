#!/bin/bash
#
# Print a log file inside one or more GitLab CI collapsible sections.
#
# GitLab's web UI refuses to collapse a section whose rendered size exceeds
# ~500 KB. GitLab Runner prepends a ~32-byte timestamp prefix to every line of
# the job trace, so a chunk's *trace* size is `file_bytes + line_count * 32`.
# We size each chunk against that trace budget (not the raw file bytes) so the
# UI always collapses every section, regardless of average line length.
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

readonly MAX_TRACE_BYTES=$((450 * 1024))  # safety margin under GitLab's 500 KB UI limit
readonly TRACE_LINE_OVERHEAD=32           # bytes added by GitLab Runner per trace line

section_start() {
  echo -e "\e[0Ksection_start:$(date +%s):${1}[collapsed=true]\r\e[0K${2}"
}

section_end() {
  echo -e "\e[0Ksection_end:$(date +%s):${1}\r\e[0K"
}

if [[ ! -f "${LOG_FILE}" ]]; then
  section_start "${SECTION_NAME}" "${SECTION_HEADER}"
  echo "Log file not found: ${LOG_FILE}"
  section_end "${SECTION_NAME}"
  exit 0
fi

size=$(wc -c <"${LOG_FILE}")
lines=$(wc -l <"${LOG_FILE}")
trace_bytes=$(( size + lines * TRACE_LINE_OVERHEAD ))
parts=$(( trace_bytes > MAX_TRACE_BYTES ? (trace_bytes + MAX_TRACE_BYTES - 1) / MAX_TRACE_BYTES : 1 ))
chunk_bytes=$(( (size + parts - 1) / parts ))

for (( i=1; i<=parts; i++ )); do
  if (( parts > 1 )); then
    name="${SECTION_NAME}_part${i}"
    header="${SECTION_HEADER} (part ${i}/${parts})"
  else
    name="${SECTION_NAME}"
    header="${SECTION_HEADER}"
  fi
  section_start "${name}" "${header}"
  dd if="${LOG_FILE}" bs="${chunk_bytes}" skip=$((i - 1)) count=1 2>/dev/null
  # Ensure the section_end marker lands on a fresh line (a chunk may not end
  # with a newline, or the file itself may not).
  echo
  section_end "${name}"
done
