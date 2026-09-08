#!/bin/bash

set -e


# scenarios getting backend data are not yet supported
NOT_SUPPORTED=("APM_TRACING_E2E_OTEL" "PARAMETRIC" "OTEL_INTEGRATIONS" "OTEL_LOG_E2E" "OTEL_METRIC_E2E" "OTEL_TRACING_E2E" "INTEGRATION_FRAMEWORKS")

if [ -d "logs/" ]; then
    echo "[DEFAULT] Running replay mode"
   ./run.sh DEFAULT --replay
fi

log_folder_prefix="logs_"

if dirs=( "$log_folder_prefix"*/ ) && [[ -d ${dirs[0]} ]]; then
  for dir in "$log_folder_prefix"*
    do
        scenario=${dir#"$log_folder_prefix"}
        scenario=$(echo "$scenario" | tr '[:lower:]' '[:upper:]')
        if [[ " ${NOT_SUPPORTED[*]} " == *" $scenario "* ]]
        then
            echo "[$scenario] Replay mode not supported "
        else
            echo "[$scenario] Running replay mode"
            ./run.sh "$scenario" --replay
        fi
    done
fi
