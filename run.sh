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
interfaces=(agent library backend)

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
    WEBLOG_ENV="DD_TRACE_SAMPLE_RATE=0.5"

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_MISSING_RULES" ]; then
    export RUNNER_ARGS=scenarios/appsec/test_customconf.py::Test_MissingRules
    export SYSTEMTESTS_LOG_FOLDER=logs_missing_appsec_rules
    WEBLOG_ENV="DD_APPSEC_RULES=/donotexists"

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_CORRUPTED_RULES" ]; then
    export RUNNER_ARGS=scenarios/appsec/test_customconf.py::Test_CorruptedRules
    export SYSTEMTESTS_LOG_FOLDER=logs_corrupted_appsec_rules
    WEBLOG_ENV="DD_APPSEC_RULES=/appsec_corrupted_rules.yml"

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_CUSTOM_RULES" ]; then
    export RUNNER_ARGS="scenarios/appsec/test_customconf.py::Test_ConfRuleSet scenarios/appsec/test_customconf.py::Test_NoLimitOnWafRules scenarios/appsec/waf/test_addresses.py scenarios/appsec/test_traces.py scenarios/appsec/test_conf.py::Test_ConfigurationVariables::test_appsec_rules"
    export SYSTEMTESTS_LOG_FOLDER=logs_custom_appsec_rules
    WEBLOG_ENV="DD_APPSEC_RULES=/appsec_custom_rules.json"

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_RULES_MONITORING_WITH_ERRORS" ]; then
    export RUNNER_ARGS="scenarios/appsec/waf/test_reports.py"
    export SYSTEMTESTS_LOG_FOLDER=logs_rules_monitoring_with_errors
    WEBLOG_ENV="DD_APPSEC_RULES=/appsec_custom_rules_with_errors.json"

elif [ $SYSTEMTESTS_SCENARIO = "PROFILING" ]; then
    export RUNNER_ARGS=scenarios/test_profiling.py
    export SYSTEMTESTS_LOG_FOLDER=logs_profiling

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_UNSUPPORTED" ]; then
    # armv7 tests
    export RUNNER_ARGS=scenarios/appsec/test_unsupported.py
    export SYSTEMTESTS_LOG_FOLDER=logs_appsec_unsupported

elif [ $SYSTEMTESTS_SCENARIO = "CGROUP" ]; then
    # cgroup test
    export RUNNER_ARGS=scenarios/test_data_integrity.py
    export SYSTEMTESTS_LOG_FOLDER=logs_cgroup

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_DISABLED" ]; then
    # disable appsec
    export RUNNER_ARGS="scenarios/test_no_ip_is_reported.py scenarios/appsec/test_conf.py::Test_ConfigurationVariables::test_disabled scenarios/appsec/test_client_ip.py"
    export SYSTEMTESTS_LOG_FOLDER=logs_appsec_disabled
    WEBLOG_ENV="DD_APPSEC_ENABLED=false"

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_LOW_WAF_TIMEOUT" ]; then
    # disable appsec
    export RUNNER_ARGS=scenarios/appsec/test_conf.py::Test_ConfigurationVariables::test_waf_timeout
    export SYSTEMTESTS_LOG_FOLDER=logs_low_waf_timeout
    WEBLOG_ENV="DD_APPSEC_WAF_TIMEOUT=1"

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_CUSTOM_OBFUSCATION" ]; then
    export RUNNER_ARGS="scenarios/appsec/test_conf.py::Test_ConfigurationVariables::test_obfuscation_parameter_key scenarios/appsec/test_conf.py::Test_ConfigurationVariables::test_obfuscation_parameter_value"
    export SYSTEMTESTS_LOG_FOLDER=logs_appsec_custom_obfuscation
    WEBLOG_ENV="DD_APPSEC_OBFUSCATION_PARAMETER_KEY_REGEXP=hide-key\nDD_APPSEC_OBFUSCATION_PARAMETER_VALUE_REGEXP=.*hide_value"

elif [ $SYSTEMTESTS_SCENARIO = "APPSEC_RATE_LIMITER" ]; then
    export RUNNER_ARGS="scenarios/appsec/test_rate_limiter.py"
    export SYSTEMTESTS_LOG_FOLDER=logs_appsec_rate_limiter
    WEBLOG_ENV="DD_APPSEC_TRACE_RATE_LIMIT=1"

elif [ $SYSTEMTESTS_SCENARIO = "LIBRARY_CONF_CUSTOM_HEADERS_SHORT" ]; then
    export RUNNER_ARGS="scenarios/test_library_conf.py::Test_HeaderTagsShortFormat"
    export SYSTEMTESTS_LOG_FOLDER=logs_library_conf_custom_headers_short
    DD_TRACE_HEADER_TAGS=$(docker run system_tests/weblog env | grep DD_TRACE_HEADER_TAGS | cut -d'=' -f2)
    WEBLOG_ENV="DD_TRACE_HEADER_TAGS=$DD_TRACE_HEADER_TAGS,header-tag1,header-tag2"

elif [ $SYSTEMTESTS_SCENARIO = "LIBRARY_CONF_CUSTOM_HEADERS_LONG" ]; then
    export RUNNER_ARGS="scenarios/test_library_conf.py::Test_HeaderTagsLongFormat"
    export SYSTEMTESTS_LOG_FOLDER=logs_library_conf_custom_headers_long
    DD_TRACE_HEADER_TAGS=$(docker run system_tests/weblog env | grep DD_TRACE_HEADER_TAGS | cut -d'=' -f2)
    WEBLOG_ENV="DD_TRACE_HEADER_TAGS=$DD_TRACE_HEADER_TAGS,header-tag1:custom.header-tag1,header-tag2:custom.header-tag2"

elif [ $SYSTEMTESTS_SCENARIO = "REMOTE_CONFIG_MOCKED_BACKEND_FEATURES" ]; then
    export RUNNER_ARGS="scenarios/remote_config/test_remote_configuration.py::Test_RemoteConfigurationFields scenarios/remote_config/test_remote_configuration.py::Test_RemoteConfigurationUpdateSequenceFeatures"
    export SYSTEMTESTS_LOG_FOLDER=logs_remote_config_mocked_backend_features
    export SYSTEMTESTS_LIBRARY_PROXY_STATE='{"mock_remote_config_backend": "FEATURES"}'

elif [ $SYSTEMTESTS_SCENARIO = "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING" ]; then
    export RUNNER_ARGS="scenarios/remote_config/test_remote_configuration.py::Test_RemoteConfigurationFields scenarios/remote_config/test_remote_configuration.py::Test_RemoteConfigurationUpdateSequenceLiveDebugging"
    export SYSTEMTESTS_LOG_FOLDER=logs_remote_config_mocked_backend_live_debugging
    export SYSTEMTESTS_LIBRARY_PROXY_STATE='{"mock_remote_config_backend": "LIVE_DEBUGGING"}'
    WEBLOG_ENV="DD_DYNAMIC_INSTRUMENTATION_ENABLED=1\nDD_DEBUGGER_ENABLED=1\nDD_REMOTE_CONFIG_ENABLED=true\nDD_INTERNAL_RCM_POLL_INTERVAL=1000"

elif [ $SYSTEMTESTS_SCENARIO = "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD" ]; then
    export RUNNER_ARGS="scenarios/remote_config/test_remote_configuration.py::Test_RemoteConfigurationFields scenarios/remote_config/test_remote_configuration.py::Test_RemoteConfigurationUpdateSequenceASMDD"
    export SYSTEMTESTS_LOG_FOLDER=logs_remote_config_mocked_backend_asm_dd
    export SYSTEMTESTS_LIBRARY_PROXY_STATE='{"mock_remote_config_backend": "ASM_DD"}'

elif [ $SYSTEMTESTS_SCENARIO = "REMOTE_CONFIG_MOCKED_BACKEND_FEATURES_NOCACHE" ]; then
    export RUNNER_ARGS="scenarios/remote_config/test_remote_configuration.py::Test_RemoteConfigurationFields scenarios/remote_config/test_remote_configuration.py::Test_RemoteConfigurationUpdateSequenceFeaturesNoCache"
    export SYSTEMTESTS_LOG_FOLDER=logs_remote_config_mocked_backend_features_nocache
    export SYSTEMTESTS_LIBRARY_PROXY_STATE='{"mock_remote_config_backend": "FEATURES_NO_CACHE"}'

elif [ $SYSTEMTESTS_SCENARIO = "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING_NOCACHE" ]; then
    export RUNNER_ARGS="scenarios/remote_config/test_remote_configuration.py::Test_RemoteConfigurationFields scenarios/remote_config/test_remote_configuration.py::Test_RemoteConfigurationUpdateSequenceLiveDebuggingNoCache"
    export SYSTEMTESTS_LOG_FOLDER=logs_remote_config_mocked_backend_live_debugging_nocache
    export SYSTEMTESTS_LIBRARY_PROXY_STATE='{"mock_remote_config_backend": "LIVE_DEBUGGING_NO_CACHE"}'
    WEBLOG_ENV="DD_DYNAMIC_INSTRUMENTATION_ENABLED=1\nDD_DEBUGGER_ENABLED=1\nDD_REMOTE_CONFIG_ENABLED=true"

elif [ $SYSTEMTESTS_SCENARIO = "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD_NOCACHE" ]; then
    export RUNNER_ARGS="scenarios/remote_config/test_remote_configuration.py::Test_RemoteConfigurationFields scenarios/remote_config/test_remote_configuration.py::Test_RemoteConfigurationUpdateSequenceASMDDNoCache"
    export SYSTEMTESTS_LOG_FOLDER=logs_remote_config_mocked_backend_asm_dd_nocache
    export SYSTEMTESTS_LIBRARY_PROXY_STATE='{"mock_remote_config_backend": "ASM_DD_NO_CACHE"}'

elif [ $SYSTEMTESTS_SCENARIO = "TRACE_PROPAGATION_STYLE_W3C" ]; then
    export RUNNER_ARGS="scenarios/test_distributed.py"
    export SYSTEMTESTS_LOG_FOLDER=logs_trace_propagation_style_w3c
    WEBLOG_ENV="DD_TRACE_PROPAGATION_STYLE_INJECT=W3C\nDD_TRACE_PROPAGATION_STYLE_EXTRACT=W3C"

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
echo -e ${WEBLOG_ENV:-} > $SYSTEMTESTS_LOG_FOLDER/.weblog.env

echo ============ Run $SYSTEMTESTS_SCENARIO tests ===================
echo "ℹ️  Log folder is ./${SYSTEMTESTS_LOG_FOLDER}"

docker inspect system_tests/weblog > $SYSTEMTESTS_LOG_FOLDER/weblog_image.json
docker inspect system_tests/agent > $SYSTEMTESTS_LOG_FOLDER/agent_image.json

echo "Starting containers in background."
docker-compose up -d --force-recreate

export container_log_folder="unset"
# Save docker logs
for container in ${containers[@]}
do
    container_log_folder="${SYSTEMTESTS_LOG_FOLDER}/docker/${container}"
    docker-compose logs --no-color --no-log-prefix -f $container > $container_log_folder/stdout.log &

    # checking container, if should not be stopped here
    if [ -z `docker ps -q --no-trunc | grep $(docker-compose ps -q $container)` ]; then
        echo "ERROR: $container container is unexpectably stopped. Here is the output:"
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
