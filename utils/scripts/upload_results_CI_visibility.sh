#!/bin/bash

set +e

if [ "$#" -ne 3 ] ; then
  echo "Script execution requires 3 parameters: environment name (dev, prod), repo origin (systest, nightly,tracer_java), pipeline run-id "
  exit 1
fi
SYS_TEST_ENV=$1
SYS_ORIGIN_REPO=$2
SYS_TEST_RUN_ID=$3

echo "Uploading test results for pipelineId-runid:${SYS_TEST_RUN_ID}"

if test -f ".env"; then
    source .env
fi

export DD_CIVISIBILITY_LOGS_ENABLED='1'
export DD_CIVISIBILITY_AGENTLESS_ENABLED='1'
export DD_SITE=datadoghq.com

#Download tool
curl -L --fail "https://github.com/DataDog/datadog-ci/releases/latest/download/datadog-ci_linux-x64" --output "$(pwd)/datadog-ci" && chmod +x $(pwd)/datadog-ci
for folder in $(find . -name "logs*" -type d -maxdepth 1); do
  if [[ -f "datadog-ci" ]]; then
      ./datadog-ci junit upload --service ci-$SYS_ORIGIN_REPO --env env-system-test-$SYS_TEST_ENV --tags "ci.pipeline.run_id:$SYS_ORIGIN_REPO-$SYS_TEST_RUN_ID" $folder/reportJunit.xml
  else
    echo "Skipping CI upload: datadog-ci not found"
  fi
done