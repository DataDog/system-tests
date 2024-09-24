#!/bin/bash
if [[ -z "${USE_NATIVE_PROFILING}" ]]; then
  exec /app/without-profiling/myproject --server.port=7777
else
  export DD_PROFILING_START_FORCE_FIRST=true # this is required to start profiling for dd-trace-java <1.39.1
  unset DD_PROFILING_START_DELAY # this shouldn't be necessary for the native image
  exec /app/with-profiling/myproject --server.port=7777
fi
