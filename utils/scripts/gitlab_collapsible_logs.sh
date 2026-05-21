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
# Chunks are partitioned on LINE boundaries (not bytes). Cutting mid-line
# leaves dangling quotes and partial fields in the trace, which can confuse
# the frontend section parser when the affected line also contains an embedded
# ISO timestamp (e.g. dockerd's `time="2026-...Z"`).
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

readonly MAX_TRACE_BYTES=$((300 * 1024))  # comfortable margin under GitLab's 500 KB UI limit
readonly TRACE_LINE_OVERHEAD=32           # bytes added by GitLab Runner per trace line

# Capture a stable timestamp once so we can advance it per-section. Distinct
# timestamps make start/end pairs trivially unique for the UI to match, even
# when many sections are emitted within the same Unix second.
section_ts=$(date +%s)
current_ts=0

section_start() {
  current_ts=$((section_ts++))
  echo -e "\e[0Ksection_start:${current_ts}:${1}[collapsed=true]\r\e[0K${2}"
}

section_end() {
  echo -e "\e[0Ksection_end:${current_ts}:${1}\r\e[0K"
}

if [[ ! -f "${LOG_FILE}" ]]; then
  section_start "${SECTION_NAME}" "${SECTION_HEADER}"
  echo "Log file not found: ${LOG_FILE}"
  section_end "${SECTION_NAME}"
  exit 0
fi

size=$(wc -c <"${LOG_FILE}")
# Use awk to count records (matches NR semantics used below), so files without
# a trailing newline still get their last line included.
lines=$(awk 'END { print NR }' "${LOG_FILE}")
[[ "${lines}" -eq 0 ]] && lines=1
trace_bytes=$(( size + lines * TRACE_LINE_OVERHEAD ))
parts=$(( trace_bytes > MAX_TRACE_BYTES ? (trace_bytes + MAX_TRACE_BYTES - 1) / MAX_TRACE_BYTES : 1 ))
lines_per_chunk=$(( (lines + parts - 1) / parts ))

for (( i=1; i<=parts; i++ )); do
  if (( parts > 1 )); then
    name="${SECTION_NAME}_part${i}"
    header="${SECTION_HEADER} (part ${i}/${parts})"
  else
    name="${SECTION_NAME}"
    header="${SECTION_HEADER}"
  fi
  start_line=$(( (i - 1) * lines_per_chunk + 1 ))
  end_line=$(( i * lines_per_chunk ))
  section_start "${name}" "${header}"
  awk -v s="${start_line}" -v e="${end_line}" 'NR>=s && NR<=e' "${LOG_FILE}"
  section_end "${name}"
done
