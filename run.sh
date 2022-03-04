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
mkdir -p logs
touch logs/.weblog.env
docker-compose down

SCENARIO=${1:-DEFAULT}

if [ $SCENARIO = "DEFAULT" ]; then  # Most common use case
    export RUNNER_ARGS=tests/
    export SYSTEMTESTS_LOG_FOLDER=logs

elif [ $SCENARIO = "SAMPLING" ]; then
    export RUNNER_ARGS=scenarios/sampling_rates.py
    export SYSTEMTESTS_LOG_FOLDER=logs_sampling_rate
    
elif [ $SCENARIO = "APPSEC_MISSING_RULES" ]; then
    export RUNNER_ARGS="scenarios/appsec/test_customconf.py::Test_MissingRules scenarios/appsec/test_customconf.py::Test_ConfRuleSet"
    export SYSTEMTESTS_LOG_FOLDER=logs_missing_appsec_rules
    WEBLOG_ENV="DD_APPSEC_RULES=/donotexists"

elif [ $SCENARIO = "APPSEC_CORRUPTED_RULES" ]; then
    export RUNNER_ARGS=scenarios/appsec/test_customconf.py::Test_CorruptedRules
    export SYSTEMTESTS_LOG_FOLDER=logs_corrupted_appsec_rules
    WEBLOG_ENV="DD_APPSEC_RULES=/appsec_corrupted_rules.yml"

elif [ $SCENARIO = "PROFILING" ]; then
    export RUNNER_ARGS=scenarios/test_profiling.py
    export SYSTEMTESTS_LOG_FOLDER=logs_profiling

elif [ $SCENARIO = "APPSEC_UNSUPPORTED" ]; then
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

echo ============ Run tests ===================
echo 🔥 Starting test context.

docker inspect system_tests/weblog > $SYSTEMTESTS_LOG_FOLDER/weblog_image.json
docker inspect system_tests/agent > $SYSTEMTESTS_LOG_FOLDER/agent_image.json

docker-compose up -d
docker-compose exec -T weblog sh -c "cat /proc/self/cgroup" > $SYSTEMTESTS_LOG_FOLDER/weblog.cgroup

# Save docker logs
for container in ${containers[@]}
do
    docker-compose logs --no-color --no-log-prefix -f $container > $SYSTEMTESTS_LOG_FOLDER/docker/$container/stdout.log &
done

# Show output. Trick: The process will end when runner ends
docker-compose logs -f runner

# Get runner status
EXIT_CODE=$(docker-compose ps -q runner | xargs docker inspect -f '{{ .State.ExitCode }}')

# Stop all containers
docker-compose down --remove-orphans

# Exit with runner's status
exit $EXIT_CODE
