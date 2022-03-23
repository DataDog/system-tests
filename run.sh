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

containers=(weblog agent runner agent_proxy library_proxy)
interfaces=(agent library)

export SYSTEMTESTS_SCENARIO=${1:-DEFAULT}
export SYSTEMTESTS_VARIATION=${2:-DEFAULT}

if [ $SYSTEMTESTS_SCENARIO != "UDS" ]; then
    export DD_AGENT_HOST=library_proxy
    export HIDDEN_APM_PORT_OVERRIDE=8126
fi

if [ $SYSTEMTESTS_SCENARIO = "DEFAULT" ]; then  # Most common use case
    export RUNNER_ARGS=tests/
    export SYSTEMTESTS_LOG_FOLDER=logs

elif [ $SYSTEMTESTS_SCENARIO = "UDS" ]; then  # Typical features but with UDS as transport
    echo "Running all tests in UDS mode."
    export RUNNER_ARGS=tests/
    export SYSTEMTESTS_LOG_FOLDER=logs_uds
    unset DD_TRACE_AGENT_PORT
    unset DD_AGENT_HOST
    export HIDDEN_APM_PORT_OVERRIDE=7126 # Break normal communication

    if [ $SYSTEMTESTS_VARIATION = "DEFAULT" ]; then
        # Test implicit config
        echo "Testing default UDS configuration path."
        unset DD_APM_RECEIVER_SOCKET
    else
       # Test explicit config
        echo "Testing explicit UDS configuration path."
        export DD_APM_RECEIVER_SOCKET=/tmp/apm.sock
    fi 

elif [ $SYSTEMTESTS_SCENARIO = "SAMPLING" ]; then
    export RUNNER_ARGS=scenarios/sampling_rates.py
    export SYSTEMTESTS_LOG_FOLDER=logs_sampling_rate
    
elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_MISSING_RULES" ]; then
    export RUNNER_ARGS=scenarios/appsec/test_customconf.py::Test_MissingRules
    export SYSTEMTESTS_LOG_FOLDER=logs_missing_appsec_rules
    WEBLOG_ENV="DD_APPSEC_RULES=/donotexists"

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_CORRUPTED_RULES" ]; then
    export RUNNER_ARGS=scenarios/appsec/test_customconf.py::Test_CorruptedRules
    export SYSTEMTESTS_LOG_FOLDER=logs_corrupted_appsec_rules
    WEBLOG_ENV="DD_APPSEC_RULES=/appsec_corrupted_rules.yml"

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_CUSTOM_RULES" ]; then
    export RUNNER_ARGS=scenarios/appsec/test_customconf.py::Test_ConfRuleSet
    export SYSTEMTESTS_LOG_FOLDER=logs_custom_appsec_rules
    WEBLOG_ENV="DD_APPSEC_RULES=/appsec_custom_rules.json"

elif [ $SYSTEMTESTS_SCENARIO = "PROFILING" ]; then
    export RUNNER_ARGS=scenarios/test_profiling.py
    export SYSTEMTESTS_LOG_FOLDER=logs_profiling

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_UNSUPPORTED" ]; then
    # armv7 tests
    export RUNNER_ARGS=scenarios/appsec/test_unsupported.py
    export SYSTEMTESTS_LOG_FOLDER=logs_appsec_unsupported

else # Let user choose the target
    export RUNNER_ARGS=$@
    export SYSTEMTESTS_LOG_FOLDER=${SYSTEMTESTS_LOG_FOLDER:-logs}
fi

# Clean logs/ folder
rm -rf $SYSTEMTESTS_LOG_FOLDER
for interface in ${interfaces[@]}
do
    mkdir -p $SYSTEMTESTS_LOG_FOLDER/interfaces/$interface
done
for container in ${containers[@]}
do
    mkdir -p $SYSTEMTESTS_LOG_FOLDER/docker/$container
done

# Image should be ready to be used, so a lot of env is set in set-system-tests-weblog-env.Dockerfile
# But some var need to be overwritten by some scenarios. We use this trick because optionnaly set 
# them in the docker-compose.yml is not possible
echo ${WEBLOG_ENV:-} > $SYSTEMTESTS_LOG_FOLDER/.weblog.env

echo ============ Run $SYSTEMTESTS_SCENARIO tests ===================
echo "ℹ️  Log folder is ./${SYSTEMTESTS_LOG_FOLDER}"

docker inspect system_tests/weblog > $SYSTEMTESTS_LOG_FOLDER/weblog_image.json
docker inspect system_tests/agent > $SYSTEMTESTS_LOG_FOLDER/agent_image.json

echo "Starting containers in background."
docker-compose up -d --force-recreate

docker-compose exec -T weblog sh -c "cat /proc/self/cgroup" > $SYSTEMTESTS_LOG_FOLDER/weblog.cgroup || true

export container_log_folder="unset"
# Save docker logs
for container in ${containers[@]}
do
    container_log_folder="${SYSTEMTESTS_LOG_FOLDER}/docker/${container}"
    docker-compose logs --no-color --no-log-prefix -f $container > $container_log_folder/stdout.log &

    # checking container, if should not be stopped here
    if [ -z `docker ps -q --no-trunc | grep $(docker-compose ps -q $container)` ]; then
        echo "ERROR: $container container is stopped. Here is the output:"
        docker-compose logs $container
        exit 1
    fi
done

echo "Outputting runner logs."

# Show output. Trick: The process will end when runner ends
docker-compose logs -f runner

# Getting runner exit code.
EXIT_CODE=$(docker-compose ps -q runner | xargs docker inspect -f '{{ .State.ExitCode }}')

# Stop all containers
docker-compose down --remove-orphans

# Exit with runner's status
echo "Exiting with ${EXIT_CODE}"
exit $EXIT_CODE
