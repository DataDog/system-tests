#!/bin/bash

set +e

if [ "$#" -ne 2 ] ; then
  echo "Script execution requires 2 parameter.  Repo Identification ,  Pipeline id + pipeline run attemp " 
  echo "Repositoriy identification examples: system-tests, night-tracer, night-agent, java-tracer, nodejs-tracer"
  exit 1
fi

SYS_ORIGIN_REPO=$1
SYS_PIPELINE_RUN_ID=$2

echo "Updating monitors with PIPELINE RUN ID $SYS_PIPELINE_RUN_ID"
SYS_UNIQUE_IDENTIFIER=$SYS_ORIGIN_REPO-$SYS_PIPELINE_RUN_ID

# Search monitor id by tag
monitor_search_resp_json=$(curl -X GET "https://api.datadoghq.com/api/v1/monitor/search?query=tag:system-tests-${SYS_ORIGIN_REPO}" \
-H "Accept: application/json" \
-H "DD-API-KEY: ${DD_API_KEY}" \
-H "DD-APPLICATION-KEY: ${DD_APP_KEY}")

monitor_id=$(jq -c '.monitors[0].id' <<< "$monitor_search_resp_json")
echo "Monitor found:${monitor_id}"

if [ $monitor_id == "null" ]; then
  echo "There is not monitor for this origin repo ${SYS_ORIGIN_REPO}"
  exit 0
fi

# Get monitor details
monitor_details_json=$(curl -X GET "https://api.datadoghq.com/api/v1/monitor/${monitor_id}" \
-H "Accept: application/json" \
-H "DD-API-KEY: ${DD_API_KEY}" \
-H "DD-APPLICATION-KEY: ${DD_APP_KEY}")

query_updated_failed_tests="{ \"query\": \"test_level:test @ci.pipeline.run_id:$SYS_UNIQUE_IDENTIFIER @test.status:fail\" }"
query_updated_flaky_tests="{ \"query\": \"test_level:test @ci.pipeline.run_id:$SYS_UNIQUE_IDENTIFIER @test.is_new_flaky:true\" }"

# Updated json adding last pipelineid
length_variables=$(jq '.options.variables | length' <<< "$monitor_details_json")

dashboard_json_updated=$(jq -r ".options.variables[0].search=$query_updated_flaky_tests" <<< "$monitor_details_json")
if [[ $length_variables > 1 ]] ; then
   dashboard_json_updated=$(jq -r ".options.variables[1].search=$query_updated_failed_tests" <<< "$dashboard_json_updated")
fi

# Update monitor adding updated json
curl -X PUT "https://api.datadoghq.com/api/v1/monitor/${monitor_id}" \
-H "Accept: application/json" \
-H "Content-Type: application/json" \
-H "DD-API-KEY: ${DD_API_KEY}" \
-H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
-d @- << EOF
$dashboard_json_updated
EOF