#!/bin/bash

NOT_SUPPPORTED=("K8S_LIB_INJECTION_BASIC" "K8S_LIB_INJECTION_FULL" "TRACE_PROPAGATION_STYLE_W3C" "APM_TRACING_E2E_OTEL")

echo "LS BEFORE"
ls -la
echo "LS DONE"
if test -f "logs/tests.log"; then
    sh run.sh DEFAULT --replay
fi

log_folder_prefix="logs_"
for dir in "$log_folder_prefix"*
do
    echo "-----> $dir <-----"
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