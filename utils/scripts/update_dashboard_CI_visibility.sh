#!/bin/bash

set +e

if [ "$#" -ne 2 ]; then
    echo "Script execution requires 2 parameter.  Repo Identification ,  Pipeline id + pipeline run attemp "
    echo "Repositoriy identification examples: system-tests, night-tracer, night-agent, tracer-java, tracer-nodejs"
    exit 1
fi

SYS_ORIGIN_REPO=$1
SYS_PIPELINE_RUN_ID=$2

echo "PIPELINE RUN ID $SYS_PIPELINE_RUN_ID"
SYS_UNIQUE_IDENTIFIER=$SYS_ORIGIN_REPO-$SYS_PIPELINE_RUN_ID

# Path parameters
export dashboard_id="zqg-kqn-2mc"

# Get dashboard json
export dashboard_json=$(
    curl -X GET "https://api.datadoghq.com/api/v1/dashboard/${dashboard_id}" \
        -H "Accept: application/json" \
        -H "DD-API-KEY: ${DD_API_KEY}" \
        -H "DD-APPLICATION-KEY: ${DD_APP_KEY}"
)

# We search for previous dashboard variable using "origin repo"
available_value_before=$(
    jq -c '.template_variables[0].available_values[]' <<<"$dashboard_json" | while read available_value; do
        if [[ $available_value == *"$SYS_ORIGIN_REPO"* ]]; then
            echo $available_value
            break
        fi
    done
)

# Json that we will to update
dashboard_variable_json=$(jq -r ".template_variables[0]" <<<"$dashboard_json")

# If we have a previous variable with the "origin repo" we will update, if it doesn't we will add
if [ -z "$available_value_before" ]; then
    echo "There is no previous value for the source repo: ${SYS_ORIGIN_REPO}"
    echo "We will add the NEW value: ${SYS_UNIQUE_IDENTIFIER}"
    dashboard_variable_json=${dashboard_variable_json//'"available_values": ['/"\"available_values\": [\"$SYS_UNIQUE_IDENTIFIER\","}
else
    echo "We will update the last variable value: ${available_value_before} to new value: ${SYS_UNIQUE_IDENTIFIER}"
    dashboard_variable_json=${dashboard_variable_json//$available_value_before/\"$SYS_UNIQUE_IDENTIFIER\"}
fi

# Updated json
dashboard_json_updated=$(jq -r ".template_variables[0]=$dashboard_variable_json" <<<"$dashboard_json")

# Commit the updated json
curl -X PUT "https://api.datadoghq.com/api/v1/dashboard/${dashboard_id}" \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -H "DD-API-KEY: ${DD_API_KEY}" \
    -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
    -d @- <<EOF
$dashboard_json_updated
EOF
