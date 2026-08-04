#!/bin/bash

set -e

# instrument.sh exports the CLR profiler variables that make the runtime load the upstream
# OpenTelemetry .NET automatic instrumentation into this process. Sourcing it is the documented
# entry point; setting CORECLR_* by hand drifts from whatever the installed version expects.
# shellcheck source=/dev/null
. /otel-dotnet-auto/instrument.sh

exec dotnet /app/app.dll
