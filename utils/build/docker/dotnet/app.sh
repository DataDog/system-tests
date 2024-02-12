#!/bin/bash

set -eu

echo starting app

#Setup Datadog APM
export ASPNETCORE_hostBuilder__reloadConfigOnChange=false
export CORECLR_ENABLE_PROFILING=1
export CORECLR_PROFILER={846F5F1C-F9AE-4B07-969E-05C26BC060D8}
export CORECLR_PROFILER_PATH=/opt/datadog/Datadog.Trace.ClrProfiler.Native.so
export DD_INTEGRATIONS=/opt/datadog/integrations.json
export DD_DOTNET_TRACER_HOME=/opt/datadog
export DD_IAST_REQUEST_SAMPLING=100
export DD_IAST_VULNERABILITIES_PER_REQUEST=100


# Dump on crash
export COMPlus_DbgEnableMiniDump=1
# MiniDumpWithPrivateReadWriteMemory is 2
export COMPlus_DbgMiniDumpType=2

if [ "${UDS_WEBLOG:-0}" = "1" ]; then
    ./set-uds-transport.sh
fi

if ( ! dotnet app.dll); then
    echo recovering dump to /var/log/system-tests/dumps 
    mkdir -p /var/log/system-tests/dumps
    find /tmp -name 'coredump*' -exec cp '{}' /var/log/system-tests/dumps \;
    chmod -R 644 /var/log/system-tests/dumps/* || true
fi
