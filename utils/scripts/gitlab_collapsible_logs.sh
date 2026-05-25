#!/bin/bash
#
# Print a log file inside one or more GitLab CI collapsible sections.
#
# GitLab's web UI refuses to collapse a section whose rendered size exceeds
# ~500 KB. GitLab Runner prepends a ~32-byte timestamp prefix to every line of
# the job trace, so a chunk's *trace* size is `sum(line_bytes + overhead)` over
# all emitted (post-wrap) lines. We split the file using a byte-accurate,
# streaming algorithm: we walk line-by-line, hard-wrap any line longer than
# MAX_LINE_BYTES, and start a new section as soon as the next emitted sub-line
# would push the running trace-byte budget over MAX_TRACE_BYTES. This bounds
# every section regardless of how line lengths are distributed across the file
# (a previous line-count-based split produced wildly uneven chunks: parts that
# happened to land where long lines clustered ballooned to 400+ KB, which the
# UI then refused to collapse).
#
# Individual file lines longer than MAX_LINE_BYTES are hard-wrapped before
# emission. The GitLab Runner trace stream is internally chunked (~8 KB) and
# the web log viewer can lose the upcoming section_end marker when a single
# trace line is multi-KB (typical victims: tracer Config{} dumps in app.log
# and containerd `starting cri plugin` JSON dumps in syslog.log).
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

readonly MAX_TRACE_BYTES=$((200 * 1024))  # generous margin under GitLab's 500 KB UI limit
readonly TRACE_LINE_OVERHEAD=32           # bytes added by GitLab Runner per trace line
readonly MAX_LINE_BYTES=1000              # wrap longer file lines; above this the UI loses section_end

# Capture a stable timestamp once. We advance it per-section (ts + part - 1)
# so consecutive start/end pairs use distinct timestamps -- this makes them
# trivially unique for the UI to match, even when emitted within the same
# Unix second.
section_ts=$(date +%s)

if [[ ! -f "${LOG_FILE}" ]]; then
  printf '\033[0Ksection_start:%d:%s[collapsed=true]\r\033[0K%s\n' \
         "${section_ts}" "${SECTION_NAME}" "${SECTION_HEADER}"
  echo "Log file not found: ${LOG_FILE}"
  printf '\033[0Ksection_end:%d:%s\r\033[0K\n' "${section_ts}" "${SECTION_NAME}"
  exit 0
fi

# First pass: byte-accurate, wrap-aware simulation that counts how many
# sections we'll produce. We need this up front so the second pass can
# emit accurate "part i/N" headers.
parts=$(awk -v max_trace="${MAX_TRACE_BYTES}" \
            -v overhead="${TRACE_LINE_OVERHEAD}" \
            -v max_line="${MAX_LINE_BYTES}" '
  BEGIN { parts = 1; used = 0 }
  function commit(sub_len,    cost) {
    cost = sub_len + 1 + overhead
    if (used > 0 && used + cost > max_trace) { parts++; used = 0 }
    used += cost
  }
  {
    line = $0
    while (length(line) > max_line) {
      commit(max_line)
      line = substr(line, max_line + 1)
    }
    commit(length(line))
  }
  END { print parts }
' "${LOG_FILE}")

[[ -z "${parts}" ]] && parts=1

# Second pass: stream the file, wrap long lines, and emit section markers
# when the next sub-line would overflow the budget. Markers are emitted from
# awk itself so the byte accounting and the section switching share state.
awk -v ts="${section_ts}" \
    -v name="${SECTION_NAME}" \
    -v header="${SECTION_HEADER}" \
    -v parts="${parts}" \
    -v max_trace="${MAX_TRACE_BYTES}" \
    -v overhead="${TRACE_LINE_OVERHEAD}" \
    -v max_line="${MAX_LINE_BYTES}" '
  BEGIN {
    esc  = sprintf("%c[0K", 27)
    cr   = sprintf("%c", 13)
    part = 1
    used = 0
    open_section()
  }
  function section_label() {
    return (parts == 1) ? name : (name "_part" part)
  }
  function header_label() {
    return (parts == 1) ? header : (header " (part " part "/" parts ")")
  }
  function open_section() {
    printf "%ssection_start:%d:%s[collapsed=true]%s%s%s\n", \
           esc, ts + part - 1, section_label(), cr, esc, header_label()
  }
  function close_section() {
    printf "%ssection_end:%d:%s%s%s\n", \
           esc, ts + part - 1, section_label(), cr, esc
  }
  function emit(sub_line,    cost) {
    cost = length(sub_line) + 1 + overhead
    if (used > 0 && used + cost > max_trace) {
      close_section()
      part++
      used = 0
      open_section()
    }
    print sub_line
    used += cost
  }
  {
    line = $0
    while (length(line) > max_line) {
      emit(substr(line, 1, max_line))
      line = substr(line, max_line + 1)
    }
    emit(line)
  }
  END { close_section() }
' "${LOG_FILE}"
