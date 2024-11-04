#!/bin/bash

set +e

if [ "$#" -eq 0 ] ; then
  echo "Script execution requires parameters:"
  echo "  -b: * job begin time (2024-10-29T18:03:39.432Z)"
  echo "  -e: * environment name (e.g., dev, prod)"
  echo "  -r: * repo origin (e.g., system-test, dd-trace-dotnet)"
  echo "  -i: * pipeline run id "
  echo "  -v: * version (e.g., 3.1.2) "
  echo "  -f: job finish time (2024-10-29T19:03:39.432Z)"
  echo "  -s: job status (Started, Success, Failure)"
  echo "  -c: job category (Build, UnitTests, PerformanceTests, EndToEndTests, Publish)"
  exit 1
fi
SYS_JOB_START_TIME=$1
SYS_TEST_ENV=$2
SYS_ORIGIN_REPO=$3
SYS_TEST_RUN_ID=$4

echo "Uploading test results for pipelineId-runid:${SYS_TEST_RUN_ID}"

if test -f ".env"; then
    source .env
fi

#Download tool
curl -L --fail "https://github.com/DataDog/datadog-ci/releases/latest/download/datadog-ci_linux-x64" --output "$(pwd)/datadog-ci" && chmod +x $(pwd)/datadog-ci
for folder in $(find . -name "logs*" -type d -maxdepth 1); do
  if [[ -f "datadog-ci" ]]; then
      ./datadog-ci junit upload --service ci-$SYS_ORIGIN_REPO --env env-system-test-$SYS_TEST_ENV --tags "ci.pipeline.run_id:$SYS_ORIGIN_REPO-$SYS_TEST_RUN_ID" $folder/reportJunit.xml
  else
    echo "Skipping CI upload: datadog-ci not found"
  fi
done