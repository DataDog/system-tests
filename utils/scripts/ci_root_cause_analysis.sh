#!/bin/bash
# Triggers a Datadog workflow to perform a CI root cause analysis for a failed pipeline.
# The workflow receives a prompt describing the failure and returns an AI-generated analysis
# formatted as a GitLab Flavored Markdown (GLFM) document written to stdout and to
# ci_root_cause_analysis.md in the current directory.
#
# Usage:
#   CI_PIPELINE_URL=<url> ./utils/scripts/ci_root_cause_analysis.sh
#   INPUT_PROMPT="Custom prompt here" ./utils/scripts/ci_root_cause_analysis.sh
#
# Environment variables:
#   DD_API_KEY       - Datadog API key (required)
#   DD_APP_KEY       - Datadog application key (required)
#   CI_PIPELINE_URL  - URL of the failed GitLab pipeline (required when INPUT_PROMPT is not set)
#   INPUT_PROMPT     - Custom prompt to send to the workflow (optional)

set -euo pipefail

WORKFLOW_ID="feb92c49-f433-48b0-954c-7ccde4a80338"
OUTPUT_FILE="ci_root_cause_analysis.md"

if [[ -z "${DD_API_KEY:-}" || -z "${DD_APP_KEY:-}" ]]; then
    echo "::error::DD_API_KEY and/or DD_APP_KEY environment variables are not set"
    exit 1
fi

PROMPT="${INPUT_PROMPT:-}"
if [[ -z "${PROMPT}" ]]; then
    PROMPT="Why did this pipeline fail? ${CI_PIPELINE_URL}"
fi

PAYLOAD="$(jq -n --arg p "${PROMPT}" '{meta: {payload: {prompt: $p}}}')"

echo "Triggering Datadog workflow ${WORKFLOW_ID} with prompt:"
echo "  ${PROMPT}"

HTTP_CODE="$(curl -sS -o response.json -w '%{http_code}' -X POST \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    -H "DD-API-KEY: ${DD_API_KEY}" \
    -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
    -d "${PAYLOAD}" \
    "https://api.datadoghq.com/api/v2/workflows/${WORKFLOW_ID}/instances")"

if [[ "${HTTP_CODE}" -lt 200 || "${HTTP_CODE}" -ge 300 ]]; then
    echo "::error::Datadog workflow trigger failed (HTTP ${HTTP_CODE})"
    cat response.json
    exit 1
fi

INSTANCE_ID="$(jq -r '.data.id' response.json)"
echo "Workflow instance created: ${INSTANCE_ID}"
echo "Polling for result..."

POLL_INTERVAL=10
MAX_WAIT=300
elapsed=0

while true; do
    sleep "${POLL_INTERVAL}"
    elapsed=$(( elapsed + POLL_INTERVAL ))

    POLL_CODE="$(curl -sS -o poll.json -w '%{http_code}' \
        -H "DD-API-KEY: ${DD_API_KEY}" \
        -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
        "https://api.datadoghq.com/api/v2/workflows/${WORKFLOW_ID}/instances/${INSTANCE_ID}")"

    if [[ "${POLL_CODE}" -lt 200 || "${POLL_CODE}" -ge 300 ]]; then
        echo "::error::Failed to poll workflow instance (HTTP ${POLL_CODE})"
        cat poll.json
        exit 1
    fi

    STATUS="$(jq -r '.data.attributes.instanceStatus.detailsKind // "unknown"' poll.json)"
    echo "  [${elapsed}s] status: ${STATUS}"

    case "${STATUS}" in
        SUCCEEDED)
            echo "Workflow completed. Generating markdown report..."
            python3 - poll.json "${OUTPUT_FILE}" << 'PYEOF'
import json
import re
import sys

poll_file = sys.argv[1]
output_file = sys.argv[2]

with open(poll_file) as f:
    d = json.load(f)

attrs = d["data"]["attributes"]
instance_id = d["data"]["id"]
status_display = attrs["instanceStatus"]["displayName"]
start_ts = attrs.get("startTimestamp", "")
end_ts = attrs.get("endTimestamp", "")
trigger_prompt = attrs.get("trigger", {}).get("prompt", "")
workflow_url = (
    attrs.get("sourceForTemplating", {}).get("api", {}).get("url", "")
)

# Extract the last non-empty assistant message from the events stream.
msg = json.loads(attrs["outputs"]["message"])
events = msg.get("events", [])

last_content = ""
for ev in reversed(events):
    payload = ev.get("payload", {})
    if payload.get("role") == "assistant" and payload.get("content", "").strip():
        last_content = payload["content"]
        break

if not last_content:
    last_content = msg.get("finalResponse", "No response available.")

# Split agent reasoning preamble from the structured analysis.
# The last assistant message uses "---" as a separator before the report headings.
split_match = re.search(r"\n\n---\n\n", last_content)
reasoning = ""
analysis = last_content
if split_match:
    reasoning = last_content[: split_match.start()].strip()
    analysis = last_content[split_match.end() :].strip()

lines: list[str] = []
lines.append("# CI Root Cause Analysis")
lines.append("")
lines.append("> [!note]")
lines.append(f"> **Prompt:** {trigger_prompt}")
lines.append("")

meta_parts = [f"**Status:** {status_display}"]
if start_ts:
    meta_parts.append(f"**Started:** {start_ts}")
if end_ts:
    meta_parts.append(f"**Completed:** {end_ts}")
if workflow_url:
    meta_parts.append(f"[View workflow instance]({workflow_url})")
lines.append(" &nbsp;|&nbsp; ".join(meta_parts))
lines.append("")
lines.append("---")
lines.append("")
lines.append(analysis)

if reasoning:
    lines.append("")
    lines.append("<details>")
    lines.append("<summary>Agent reasoning steps</summary>")
    lines.append("")
    lines.append(reasoning)
    lines.append("")
    lines.append("</details>")

lines.append("")
output = "\n".join(lines)

with open(output_file, "w") as f:
    f.write(output)

print(output)
PYEOF
            echo ""
            echo "Report written to ${OUTPUT_FILE}"
            exit 0
            ;;
        FAILED|ERROR)
            echo "::error::Workflow instance failed"
            jq '.' poll.json
            exit 1
            ;;
        *)
            if [[ "${elapsed}" -ge "${MAX_WAIT}" ]]; then
                echo "::error::Timed out waiting for workflow result after ${MAX_WAIT}s"
                jq '.' poll.json
                exit 1
            fi
            ;;
    esac
done
