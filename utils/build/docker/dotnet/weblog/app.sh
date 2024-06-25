#!/bin/bash

set -eu

echo 'starting app'

# Enable Datadog .NET SDK
export CORECLR_ENABLE_PROFILING=1
export CORECLR_PROFILER='{846F5F1C-F9AE-4B07-969E-05C26BC060D8}'
export CORECLR_PROFILER_PATH=/opt/datadog/linux-x64/Datadog.Trace.ClrProfiler.Native.so
export DD_DOTNET_TRACER_HOME=/opt/datadog

# Datadog .NET SDK config
export DD_IAST_REQUEST_SAMPLING=100
export DD_IAST_VULNERABILITIES_PER_REQUEST=100
export DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
export DD_DATA_STREAMS_ENABLED=true
export DD_INTERNAL_TELEMETRY_V2_ENABLED=true

# .NET runtime config
export ASPNETCORE_hostBuilder__reloadConfigOnChange=false
export COMPlus_DbgEnableMiniDump=1 # Enable dump on crash
export COMPlus_DbgMiniDumpType=2   # MiniDumpWithPrivateReadWriteMemory is 2

if [ "${UDS_WEBLOG:-0}" = "1" ]; then
    export DD_APM_RECEIVER_SOCKET=/var/run/datadog/apm.socket
    ./set-uds-transport.sh
fi

if ( ! dotnet app.dll); then
    echo recovering dump to /var/log/system-tests/dumps
    mkdir -p /var/log/system-tests/dumps
    find /tmp -name 'coredump*' -exec cp '{}' /var/log/system-tests/dumps \;
    chmod -R 644 /var/log/system-tests/dumps/* || true
fi
