if [ "$#" -ne 1 ] ; then
  echo "Script execution requires one parameter: Pipeline id" 
  exit 1
fi
SYS_PIPELINE_ID=$1

echo "PIPELINE ID $SYS_PIPELINE_ID"

# Path parameters
export dashboard_id="zqg-kqn-2mc"

dashboard_json=$(
curl -X GET "https://api.datadoghq.com/api/v1/dashboard/${dashboard_id}" \
-H "Accept: application/json" \
-H "DD-API-KEY: ${DD_API_KEY}" \
-H "DD-APPLICATION-KEY: ${DD_APP_KEY}")

dashboard_json_updated=$(jq -r ".template_variables[0].default = \"$SYS_PIPELINE_ID\""  <<< "$dashboard_json")



curl -X PUT "https://api.datadoghq.com/api/v1/dashboard/${dashboard_id}" \
-H "Accept: application/json" \
-H "Content-Type: application/json" \
-H "DD-API-KEY: ${DD_API_KEY}" \
-H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
-d @- << EOF
$dashboard_json_updated
EOF