#!/bin/bash

set -e


# scenario getting backedn data are not yet supported
NOT_SUPPPORTED=("K8S_LIB_INJECTION_BASIC" "K8S_LIB_INJECTION_FULL" "APM_TRACING_E2E_OTEL" "PARAMETRIC")

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
        if [[ ${NOT_SUPPPORTED[*]} =~ $scenario ]]
        then
            echo "[$scenario] Replay mode not supported "
        else
            echo "[$scenario] Running replay mode"
            ./run.sh "$scenario" --replay
        fi
    done
fi
