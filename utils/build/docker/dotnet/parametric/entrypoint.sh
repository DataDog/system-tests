#!/bin/bash
set -e

# Conditionally set LD_PRELOAD for the continuous profiler.
# The ApiWrapper.x64.so is x86_64-only and crashes on ARM,
# so only preload it when the file actually exists.
if [ -f /opt/datadog/continuousprofiler/Datadog.Linux.ApiWrapper.x64.so ]; then
  export LD_PRELOAD=/opt/datadog/continuousprofiler/Datadog.Linux.ApiWrapper.x64.so
fi

if [ -n "${TEST_LOCALE:-}" ]; then
  export LD_PRELOAD="${LD_PRELOAD:+$LD_PRELOAD:}/locale_init.so"
fi

exec "$@"
