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

CONTAINERS=(weblog agent runner agent_proxy library_proxy)
interfaces=(agent library backend)
WEBLOG_ENV="DD_APPSEC_ENABLED=true\n"

export SYSTEMTESTS_SCENARIO=${1:-DEFAULT}
export SYSTEMTESTS_VARIATION=${2:-DEFAULT}

if [ $SYSTEMTESTS_SCENARIO != "UDS" ]; then
    export DD_AGENT_HOST=library_proxy
    export HIDDEN_APM_PORT_OVERRIDE=8126
fi

export RUNNER_ARGS="tests/"
export SYSTEMTESTS_LOG_FOLDER="logs_$(echo $SYSTEMTESTS_SCENARIO | tr '[:upper:]' '[:lower:]')"

if [ $SYSTEMTESTS_SCENARIO = "DEFAULT" ]; then  # Most common use case
    export SYSTEMTESTS_LOG_FOLDER=logs
    CONTAINERS+=(postgres)

elif [ $SYSTEMTESTS_SCENARIO = "UDS" ]; then  # Typical features but with UDS as transport
    echo "Running all tests in UDS mode."
    CONTAINERS+=(postgres)
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
    WEBLOG_ENV+="DD_TRACE_SAMPLE_RATE=0.5"

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_MISSING_RULES" ]; then
    WEBLOG_ENV+="DD_APPSEC_RULES=/donotexists"

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_CORRUPTED_RULES" ]; then
    WEBLOG_ENV+="DD_APPSEC_RULES=/appsec_corrupted_rules.yml"

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_CUSTOM_RULES" ]; then
    WEBLOG_ENV+="DD_APPSEC_RULES=/appsec_custom_rules.json"

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_RULES_MONITORING_WITH_ERRORS" ]; then
    WEBLOG_ENV+="DD_APPSEC_RULES=/appsec_custom_rules_with_errors.json"

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
    WEBLOG_ENV="DD_APPSEC_ENABLED=false"

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_LOW_WAF_TIMEOUT" ]; then
    # disable appsec
    WEBLOG_ENV+="DD_APPSEC_WAF_TIMEOUT=1"

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_CUSTOM_OBFUSCATION" ]; then
    WEBLOG_ENV+="DD_APPSEC_OBFUSCATION_PARAMETER_KEY_REGEXP=hide-key\nDD_APPSEC_OBFUSCATION_PARAMETER_VALUE_REGEXP=.*hide_value"

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_RATE_LIMITER" ]; then
    WEBLOG_ENV+="DD_APPSEC_TRACE_RATE_LIMIT=1"

elif [ $SYSTEMTESTS_SCENARIO = "LIBRARY_CONF_CUSTOM_HEADERS_SHORT" ]; then
    DD_TRACE_HEADER_TAGS=$(docker run system_tests/weblog env | grep DD_TRACE_HEADER_TAGS | cut -d'=' -f2)
    WEBLOG_ENV+="DD_TRACE_HEADER_TAGS=$DD_TRACE_HEADER_TAGS,header-tag1,header-tag2"

elif [ $SYSTEMTESTS_SCENARIO = "LIBRARY_CONF_CUSTOM_HEADERS_LONG" ]; then
    DD_TRACE_HEADER_TAGS=$(docker run system_tests/weblog env | grep DD_TRACE_HEADER_TAGS | cut -d'=' -f2)
    WEBLOG_ENV+="DD_TRACE_HEADER_TAGS=$DD_TRACE_HEADER_TAGS,header-tag1:custom.header-tag1,header-tag2:custom.header-tag2"

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_IP_BLOCKING" ]; then
    export SYSTEMTESTS_LIBRARY_PROXY_STATE='{"mock_remote_config_backend": "ASM_DATA"}'

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_RUNTIME_ACTIVATION" ]; then
    export SYSTEMTESTS_LIBRARY_PROXY_STATE='{"mock_remote_config_backend": "ASM_ACTIVATE_ONLY"}'
    # Override WEBLOG_ENV to remove DD_APPSEC_ENABLED=true
    WEBLOG_ENV="DD_RC_TARGETS_KEY_ID=TEST_KEY_ID\nDD_RC_TARGETS_KEY=1def0961206a759b09ccdf2e622be20edf6e27141070e7b164b7e16e96cf402c\nDD_REMOTE_CONFIG_INTEGRITY_CHECK_ENABLED=true"

elif [ $SYSTEMTESTS_SCENARIO = "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES" ]; then
    export SYSTEMTESTS_LIBRARY_PROXY_STATE='{"mock_remote_config_backend": "ASM_FEATURES"}'
    # Override WEBLOG_ENV to remove DD_APPSEC_ENABLED=true
    WEBLOG_ENV="DD_REMOTE_CONFIGURATION_ENABLED=true"

elif [ $SYSTEMTESTS_SCENARIO = "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING" ]; then
    export SYSTEMTESTS_LIBRARY_PROXY_STATE='{"mock_remote_config_backend": "LIVE_DEBUGGING"}'
    WEBLOG_ENV+="DD_DYNAMIC_INSTRUMENTATION_ENABLED=1\nDD_DEBUGGER_ENABLED=1\nDD_REMOTE_CONFIG_ENABLED=true\nDD_INTERNAL_RCM_POLL_INTERVAL=1000"

elif [ $SYSTEMTESTS_SCENARIO = "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD" ]; then
    export SYSTEMTESTS_LIBRARY_PROXY_STATE='{"mock_remote_config_backend": "ASM_DD"}'

elif [ $SYSTEMTESTS_SCENARIO = "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES_NOCACHE" ]; then
    export SYSTEMTESTS_LIBRARY_PROXY_STATE='{"mock_remote_config_backend": "ASM_FEATURES_NO_CACHE"}'
    WEBLOG_ENV="DD_REMOTE_CONFIGURATION_ENABLED=true"

elif [ $SYSTEMTESTS_SCENARIO = "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING_NOCACHE" ]; then
    export SYSTEMTESTS_LIBRARY_PROXY_STATE='{"mock_remote_config_backend": "LIVE_DEBUGGING_NO_CACHE"}'
    WEBLOG_ENV+="DD_DYNAMIC_INSTRUMENTATION_ENABLED=1\nDD_DEBUGGER_ENABLED=1\nDD_REMOTE_CONFIG_ENABLED=true"

elif [ $SYSTEMTESTS_SCENARIO = "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD_NOCACHE" ]; then
    export SYSTEMTESTS_LIBRARY_PROXY_STATE='{"mock_remote_config_backend": "ASM_DD_NO_CACHE"}'

elif [ $SYSTEMTESTS_SCENARIO = "TRACE_PROPAGATION_STYLE_W3C" ]; then
    WEBLOG_ENV+="DD_TRACE_PROPAGATION_STYLE_INJECT=W3C\nDD_TRACE_PROPAGATION_STYLE_EXTRACT=W3C"

elif [ $SYSTEMTESTS_SCENARIO = "INTEGRATIONS" ]; then
    CONTAINERS+=(cassandra_db mongodb)

else # Let user choose the target
    export SYSTEMTESTS_SCENARIO="CUSTOM"
    export RUNNER_ARGS=$@
    export SYSTEMTESTS_LOG_FOLDER=logs
    CONTAINERS+=(postgres)
fi
# Clean logs/ folder
rm -rf $SYSTEMTESTS_LOG_FOLDER
for interface in ${interfaces[@]}
do
    mkdir -p $SYSTEMTESTS_LOG_FOLDER/interfaces/$interface
done
for CONTAINER in ${CONTAINERS[@]}
do
    mkdir -p $SYSTEMTESTS_LOG_FOLDER/docker/$CONTAINER
done

# Image should be ready to be used, so a lot of env is set in set-system-tests-weblog-env.Dockerfile
# But some var need to be overwritten by some scenarios. We use this trick because optionnaly set
# them in the docker-compose.yml is not possible
echo -e ${WEBLOG_ENV:-} > $SYSTEMTESTS_LOG_FOLDER/.weblog.env

echo ============ Run $SYSTEMTESTS_SCENARIO tests ===================
echo "ℹ️  Log folder is ./${SYSTEMTESTS_LOG_FOLDER}"

docker inspect system_tests/weblog > $SYSTEMTESTS_LOG_FOLDER/weblog_image.json
docker inspect system_tests/agent > $SYSTEMTESTS_LOG_FOLDER/agent_image.json

echo "Starting containers in background"
docker-compose up -d --force-recreate ${CONTAINERS[*]}

export container_log_folder="unset"
# Save docker logs
for CONTAINER in ${CONTAINERS[@]}
do
    container_log_folder="${SYSTEMTESTS_LOG_FOLDER}/docker/${CONTAINER}"
    docker-compose logs --no-color --no-log-prefix -f $CONTAINER > $container_log_folder/stdout.log &

    # checking container, if should not be stopped here
    if [ -z `docker ps -q --no-trunc | grep $(docker-compose ps -q $CONTAINER)` ]; then
        echo "ERROR: $CONTAINER container is unexpectably stopped. Here is the output:"
        docker-compose logs $CONTAINER
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
