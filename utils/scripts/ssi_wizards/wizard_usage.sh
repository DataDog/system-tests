#!/usr/bin/env bash

# Usage logs for the SSI wizards. One log per milestone.
# Set SSI_WIZARD_TELEMETRY=off to disable. Set it to dry-run to print the JSON.

wizard_usage_step() {
    WIZARD_LAST_STEP="$1"
    export WIZARD_LAST_STEP
}

wizard_usage_begin() {
    WIZARD_NAME="$1"
    WIZARD_SESSION_ID="$(uuidgen 2>/dev/null || echo "$$-$(date +%s)")"
    WIZARD_START_TS="$(date +%s)"
    WIZARD_USAGE_DONE=""
    WIZARD_LAST_STEP="start"
    export WIZARD_NAME WIZARD_SESSION_ID WIZARD_START_TS WIZARD_LAST_STEP
    trap wizard_usage_on_exit EXIT
    wizard_usage wizard.started
}

wizard_usage_on_exit() {
    local rc=$?
    if [[ -z "${WIZARD_USAGE_DONE:-}" ]]; then
        wizard_usage wizard.aborted "exit_code=${rc}"
    fi
    return "${rc}"
}

# Marks the run as finished so the EXIT trap does not also send wizard.aborted.
wizard_usage_finish() {
    WIZARD_USAGE_DONE=1
    wizard_usage "$@"
}

# wizard_usage <event> [key=value ...]
# Keys are stored under the "wizard" object. Nothing outside this list is read.
wizard_usage() {
    local mode="${SSI_WIZARD_TELEMETRY:-on}"
    if [[ "${mode}" == "off" ]]; then
        return 0
    fi

    local event="$1"
    shift

    local payload_file
    payload_file="$(mktemp)" || return 0

    # shellcheck disable=SC2016  # the Python program is not shell
    if ! WIZARD_EVENT="${event}" python3 - "$@" >"${payload_file}" <<'PY'
import json
import os
import platform
import re
import subprocess
import sys
import time


def git(*args):
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, timeout=2, check=False)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


event = os.environ["WIZARD_EVENT"]
name = os.environ.get("WIZARD_NAME", "unknown")
start = int(os.environ.get("WIZARD_START_TS") or "0")
wizard = {
    "name": name,
    "session_id": os.environ.get("WIZARD_SESSION_ID", ""),
    "elapsed_s": int(time.time()) - start,
    "last_step": os.environ.get("WIZARD_LAST_STEP", ""),
    "commit": git("rev-parse", "--short", "HEAD"),
}
for item in sys.argv[1:]:
    key, sep, value = item.partition("=")
    if sep == "":
        continue
    wizard[key] = int(value) if re.fullmatch(r"-?\d+", value) else value

tags = ["wizard:" + name, "event:" + event]
for key in ("library", "outcome"):
    if wizard.get(key):
        tags.append(key + ":" + str(wizard[key]))

email = git("config", "user.email") or os.environ.get("USER", "unknown")
print(json.dumps([{
    "message": name + " wizard: " + event,
    "service": "ssi-wizard",
    "ddsource": "system-tests",
    "ddtags": ",".join(tags),
    "evt": {"name": event},
    "usr": {"email": email},
    "wizard": wizard,
    "host_os": platform.system().lower(),
    "host_arch": platform.machine(),
}]))
PY
    then
        rm -f "${payload_file}"
        return 0
    fi

    if [[ "${mode}" == "dry-run" ]]; then
        cat "${payload_file}"
        rm -f "${payload_file}"
        return 0
    fi

    if ! command -v dd-auth >/dev/null 2>&1; then
        rm -f "${payload_file}"
        return 0
    fi

    local domain="${SSI_WIZARD_TELEMETRY_DOMAIN:-app.datadoghq.com}"
    # Single quotes on purpose: the inner shell, after dd-auth, expands DD_API_KEY and DD_SITE.
    # shellcheck disable=SC2016
    DD_AUTH_API_KEY=1 dd-auth --domain "${domain}" -- bash -c \
        'curl -sS -m 5 -o /dev/null -X POST -H "DD-API-KEY: $DD_API_KEY" -H "Content-Type: application/json" "https://http-intake.logs.${DD_SITE}/api/v2/logs" --data @"$1"' \
        _ "${payload_file}" >/dev/null 2>&1 || true
    rm -f "${payload_file}"
}
