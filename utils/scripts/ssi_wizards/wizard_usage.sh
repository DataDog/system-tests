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
    WIZARD_LIBRARY="${TEST_LIBRARY:-}"
    export WIZARD_NAME WIZARD_SESSION_ID WIZARD_START_TS WIZARD_LAST_STEP WIZARD_LIBRARY
    trap wizard_usage_on_exit EXIT
    wizard_usage wizard.started
}

wizard_usage_on_exit() {
    local rc=$?
    if [[ -z "${WIZARD_USAGE_DONE:-}" ]]; then
        wizard_usage wizard.aborted "exit_code=${rc}" "outcome=aborted"
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

library = os.environ.get("WIZARD_LIBRARY", "")
if library and "library" not in wizard:
    wizard["library"] = library
for key, env_name in (("scenario", "WIZARD_SCENARIO"), ("weblog", "WIZARD_WEBLOG")):
    remembered = os.environ.get(env_name, "")
    if remembered and key not in wizard:
        wizard[key] = remembered

def tag_value(value: object) -> str:
    cleaned = []
    for char in str(value).strip().lower():
        if char.isalnum() or char in "_.-/":
            cleaned.append(char)
        else:
            cleaned.append("_")
    return "".join(cleaned).strip("_.-/")


tags = ["wizard:" + name, "event:" + event]
for key in ("library", "outcome", "last_step", "scenario", "weblog"):
    if wizard.get(key):
        safe = tag_value(wizard[key])
        if safe:
            tags.append(key + ":" + safe)

email = git("config", "user.email") or os.environ.get("USER", "unknown")
safe_email = tag_value(email)
if safe_email:
    tags.append("usr_email:" + safe_email)
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
        wizard_usage_trace "dry-run" "${event}"
        cat "${payload_file}"
        rm -f "${payload_file}"
        return 0
    fi

    if ! command -v dd-auth >/dev/null 2>&1; then
        if [[ -z "${WIZARD_USAGE_NO_AUTH:-}" ]]; then
            WIZARD_USAGE_NO_AUTH=1
            wizard_usage_trace "skipped" "${event}" "dd-auth is not installed"
        fi
        rm -f "${payload_file}"
        return 0
    fi

    wizard_usage_trace "sending" "${event}"
    local domain="${SSI_WIZARD_TELEMETRY_DOMAIN:-app.datadoghq.com}"
    local status=""
    # Single quotes on purpose: the inner shell, after dd-auth, expands DD_API_KEY and DD_SITE.
    # The key is written to curl's stdin so it is not part of the process arguments.
    # shellcheck disable=SC2016
    status="$(
        DD_AUTH_API_KEY=1 dd-auth --domain "${domain}" -- bash -c \
            'printf "DD-API-KEY: %s\n" "$DD_API_KEY" | curl -sS -m 5 -o /dev/null -w "%{http_code}" -X POST -H @- -H "Content-Type: application/json" "https://http-intake.logs.${DD_SITE}/api/v2/logs" --data @"$1"' \
            _ "${payload_file}" 2>/dev/null | tail -n 1
    )" || status=""
    status="${status//[[:space:]]/}"
    rm -f "${payload_file}"

    if [[ "${status}" =~ ^2 ]]; then
        wizard_usage_trace "sent" "${event}"
    else
        wizard_usage_trace "not-sent" "${event}"
    fi
}

# One short line so a run shows that usage data is leaving the laptop.
# "sending" stays on the same line until "sent" or "not-sent" replaces it.
# outcome is sending, sent, not-sent, dry-run or skipped.
wizard_usage_trace() {
    local outcome="$1"
    local event="$2"
    local detail="${3:-}"
    local cyan="${CYAN:-\033[1;36m}"
    local green="${GREEN:-\033[0;32m}"
    local yellow="${YELLOW:-\033[1;33m}"
    local nc="${NC:-\033[0m}"

    case "${outcome}" in
        sending)
            # stderr is unbuffered, so the line shows before the API call returns.
            printf '%b' "${cyan}📡 Sending wizard usage: ${event}...${nc}" >&2
            ;;
        sent)
            printf '\r%b\n' "${green}📡 Wizard usage sent: ${event}${nc}    " >&2
            ;;
        not-sent)
            printf '\r%b\n' "${yellow}📡 Wizard usage not sent: ${event}${nc}    " >&2
            ;;
        dry-run)
            printf '%b\n' "${cyan}📡 Wizard usage (dry-run): ${event}${nc}" >&2
            ;;
        skipped)
            printf '%b\n' "${yellow}📡 Wizard usage skipped: ${detail}${nc}" >&2
            ;;
        *) return 0 ;;
    esac
}
