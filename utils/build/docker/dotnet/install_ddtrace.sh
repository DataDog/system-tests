#!/bin/bash
set -eu

mkdir -p /opt/datadog
tar xzf $(ls datadog-dotnet-apm-*.tar.gz) -C /opt/datadog

if [ $(ls /LIBRARY_VERSION | wc -l) = 0 ]; then
    ls datadog-dotnet-apm-*.tar.gz > /LIBRARY_VERSION
    LD_LIBRARY_PATH=/opt/datadog dotnet fsi --langversion:preview /query-versions.fsx
fi

echo "dd-trace version: $(cat /LIBRARY_VERSION)"
echo "libddwaf version: $(cat /LIBDDWAF_VERSION)"
echo "appsec event rules version: $(cat /APPSEC_EVENT_RULES_VERSION)"