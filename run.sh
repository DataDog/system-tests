#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

set -eu

# set .env if exists. Allow users to keep their conf via env vars
if test -f ".env"; then
    source .env
fi

if [ -z "${DD_API_KEY:-}" ]; then
    echo "DD_API_KEY is missing in env, please add it."
    exit 1
fi

interfaces=(agent library backend)

export SYSTEMTESTS_SCENARIO=${1:-DEFAULT}
export HOST_PWD=$(pwd)

export DD_AGENT_HOST=runner
export RUNNER_ARGS="tests/"
export SYSTEMTESTS_LOG_FOLDER="logs_$(echo $SYSTEMTESTS_SCENARIO | tr '[:upper:]' '[:lower:]')"

if [ $SYSTEMTESTS_SCENARIO = "DEFAULT" ]; then  # Most common use case
    export SYSTEMTESTS_LOG_FOLDER=logs

elif [ $SYSTEMTESTS_SCENARIO = "SAMPLING" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_MISSING_RULES" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_CORRUPTED_RULES" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_CUSTOM_RULES" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_BLOCKING" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_RULES_MONITORING_WITH_ERRORS" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "PROFILING" ]; then
    # big timeout
    echo

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_UNSUPPORTED" ]; then # armv7 tests
    # we'll probably need to remove this one
    echo
    
elif [ $SYSTEMTESTS_SCENARIO = "CGROUP" ]; then
    # cgroup test
    # require a dedicated warmup. Need to check the stability before 
    # merging it into the default scenario
    echo

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_DISABLED" ]; then
    # disable appsec
    echo

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_LOW_WAF_TIMEOUT" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_CUSTOM_OBFUSCATION" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_RATE_LIMITER" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "LIBRARY_CONF_CUSTOM_HEADERS_SHORT" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "LIBRARY_CONF_CUSTOM_HEADERS_LONG" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_IP_BLOCKING" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_RUNTIME_ACTIVATION" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES_NOCACHE" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING_NOCACHE" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD_NOCACHE" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "TRACE_PROPAGATION_STYLE_W3C" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "INTEGRATIONS" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_WAF_TELEMETRY" ]; then
    echo

elif [ $SYSTEMTESTS_SCENARIO = "APM_TRACING_E2E" ]; then
    export RUNNER_ARGS="tests/apm_tracing_e2e"

elif [ $SYSTEMTESTS_SCENARIO = "APM_TRACING_E2E_SINGLE_SPAN" ]; then
    export RUNNER_ARGS="tests/apm_tracing_e2e"

else # Let user choose the target
    export SYSTEMTESTS_SCENARIO="CUSTOM"
    export RUNNER_ARGS=$@
    export SYSTEMTESTS_LOG_FOLDER=logs
fi

# clean any pycache folder
find utils tests -type d -name '__pycache__'  -prune -exec rm -rf {} +

# Clean logs/ folder
rm -rf $SYSTEMTESTS_LOG_FOLDER

for interface in ${interfaces[@]}
do
    mkdir -p $SYSTEMTESTS_LOG_FOLDER/interfaces/$interface
done

mkdir -p $SYSTEMTESTS_LOG_FOLDER/docker/runner
mkdir -p $SYSTEMTESTS_LOG_FOLDER/docker/weblog/logs
chmod -R 777 $SYSTEMTESTS_LOG_FOLDER

echo ============ Run $SYSTEMTESTS_SCENARIO tests ===================
echo "ℹ️  Log folder is ./${SYSTEMTESTS_LOG_FOLDER}"

docker inspect system_tests/weblog > $SYSTEMTESTS_LOG_FOLDER/weblog_image.json
docker inspect system_tests/agent > $SYSTEMTESTS_LOG_FOLDER/agent_image.json

export WEBLOG_ENV
docker-compose up --force-recreate runner
docker-compose logs runner > $SYSTEMTESTS_LOG_FOLDER/docker/runner/stdout.log

# Getting runner exit code.
EXIT_CODE=$(docker-compose ps -q runner | xargs docker inspect -f '{{ .State.ExitCode }}')

# Stop all containers
docker-compose down --remove-orphans

# Exit with runner's status
echo "Exiting with ${EXIT_CODE}"
exit $EXIT_CODE
