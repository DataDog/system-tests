#!/usr/bin/env bash

set -eu

injector_root=/opt/datadog-packages/datadog-apm-inject/stable
launcher="$(readlink -f "${injector_root}/inject/launcher.preload.so")"

if [[ -z "${DD_TRACE_AGENT_URL:-}" ]]; then
    agent_host="${DD_AGENT_HOST:-127.0.0.1}"
    agent_port="${DD_TRACE_AGENT_PORT:-8126}"
    if [[ "$agent_host" == *:* && "$agent_host" != \[*\] ]]; then
        agent_host="[${agent_host}]"
    fi
    export DD_TRACE_AGENT_URL="http://${agent_host}:${agent_port}"
fi

export LD_PRELOAD="${launcher}${LD_PRELOAD:+:${LD_PRELOAD}}"
exec python3 /app/server.py
