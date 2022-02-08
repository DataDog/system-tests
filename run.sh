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

# Stop previous container not stopped
docker-compose down

# Set default docker compose file to be overridden if needed
export TESTS_DOCKER_COMPOSE_FILE=docker-compose.yml

SCENARIO=${1:-DEFAULT}

if [ $SCENARIO = "DEFAULT" ]; then  # Most common use case
    export RUNNER_ARGS=tests/
    export SYSTEMTESTS_LOG_FOLDER=logs
    export TESTS_DOCKER_COMPOSE=uds-docker-compose.yml # remove after verifying

if [ $SCENARIO = "UDS" ]; then  # Typical features but with UDS as transport
    export RUNNER_ARGS=tests/
    export SYSTEMTESTS_LOG_FOLDER=logs
    export TESTS_DOCKER_COMPOSE=uds-docker-compose.yml

elif [ $SCENARIO = "SAMPLING" ]; then
    export RUNNER_ARGS=scenarios/sampling_rates.py
    export SYSTEMTESTS_LOG_FOLDER=logs_sampling_rate
    
elif [ $SCENARIO = "APPSEC_MISSING_RULES" ]; then
    export RUNNER_ARGS=scenarios/appsec/test_logs.py::Test_ErrorStandardization::test_c04
    export SYSTEMTESTS_LOG_FOLDER=logs_missing_appsec_rules
    export DD_APPSEC_RULES=/donotexists

elif [ $SCENARIO = "APPSEC_CORRUPTED_RULES" ]; then
    export RUNNER_ARGS=scenarios/appsec/test_logs.py::Test_ErrorStandardization::test_c05
    export SYSTEMTESTS_LOG_FOLDER=logs_corrupted_appsec_rules
    export DD_APPSEC_RULES=/appsec_corrupted_rules.yml

elif [ $SCENARIO = "APPSEC_UNSUPPORTED" ]; then
    export RUNNER_ARGS=scenarios/appsec_unsupported.py
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

echo ============ Run tests ===================
echo 🔥 Starting test context.

docker inspect system_tests/weblog > $SYSTEMTESTS_LOG_FOLDER/weblog_image.json
docker inspect system_tests/agent > $SYSTEMTESTS_LOG_FOLDER/agent_image.json

docker-compose -f ${TESTS_DOCKER_COMPOSE_FILE} $ up -d
docker-compose exec -T weblog sh -c "cat /proc/self/cgroup" > $SYSTEMTESTS_LOG_FOLDER/weblog.cgroup

# Save docker logs
for container in ${containers[@]}
do
    docker-compose logs --no-color -f $container > $SYSTEMTESTS_LOG_FOLDER/docker/$container/stdout.log &
done

# Show output. Trick: The process will end when runner ends
docker-compose logs -f runner

# Get runner status
EXIT_CODE=$(docker-compose ps -q runner | xargs docker inspect -f '{{ .State.ExitCode }}')

# Stop all containers
docker-compose down --remove-orphans

# Exit with runner's status
exit $EXIT_CODE
