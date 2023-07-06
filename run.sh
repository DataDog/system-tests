#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

set -eu

# clean any pycache folder
find utils tests -type d -name '__pycache__'  -prune -exec rm -rf {} +

if [[ -z "${IN_NIX_SHELL:-}" ]]; then
   source venv/bin/activate
fi

# All the purpose if this script is to handle set of scenarios
# convention: a set of scenarios must ends with _SCENARIOS

APPSEC_SCENARIOS=(
    APPSEC_MISSING_RULES
    APPSEC_CORRUPTED_RULES
    APPSEC_CUSTOM_RULES
    APPSEC_BLOCKING
    APPSEC_RULES_MONITORING_WITH_ERRORS
    APPSEC_DISABLED
    APPSEC_CUSTOM_OBFUSCATION
    APPSEC_RATE_LIMITER
    APPSEC_WAF_TELEMETRY
    APPSEC_BLOCKING_FULL_DENYLIST
    APPSEC_REQUEST_BLOCKING
    APPSEC_RUNTIME_ACTIVATION
)

REMOTE_CONFIG_SCENARIOS=(
    REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD
    REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD_NOCACHE
    REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES
    REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES_NOCACHE
    REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING
    REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING_NOCACHE
)

TELEMETRY_SCENARIOS=(
    TELEMETRY_MESSAGE_BATCH_EVENT_ORDER
    TELEMETRY_APP_STARTED_PRODUCTS_DISABLED
    TELEMETRY_DEPENDENCY_LOADED_TEST_FOR_DEPENDENCY_COLLECTION_DISABLED
    TELEMETRY_LOG_GENERATION_DISABLED
    TELEMETRY_METRIC_GENERATION_DISABLED
)

# Scenarios to run before a tracer release, basically, all stable scenarios
TRACER_RELEASE_SCENARIOS=(
    DEFAULT 
    TRACE_PROPAGATION_STYLE_W3C 
    PROFILING 
    LIBRARY_CONF_CUSTOM_HEADERS_SHORT 
    LIBRARY_CONF_CUSTOM_HEADERS_LONG
    INTEGRATIONS
    APM_TRACING_E2E_SINGLE_SPAN
    APM_TRACING_E2E 
    APM_TRACING_E2E_OTEL
    "${APPSEC_SCENARIOS[@]}"
    "${REMOTE_CONFIG_SCENARIOS[@]}"
    "${TELEMETRY_SCENARIOS[@]}"
)

# Scenarios to run on tracers PR.
# Those scenarios are the one that offer the best probability-to-catch-bug/time-to-run ratio
TRACER_ESSENTIAL_SCENARIOS=(
    DEFAULT
    APPSEC_BLOCKING
    REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES
    TELEMETRY_MESSAGE_BATCH_EVENT_ORDER
    INTEGRATIONS
)

ONBOARDING_SCENARIOS=(
    ONBOARDING_HOST
    ONBOARDING_HOST_CONTAINER
    ONBOARDING_CONTAINER
)
 
DEBUGGER_SCENARIOS=(
    DEBUGGER_METHOD_PROBES_STATUS
    DEBUGGER_LINE_PROBES_STATUS
)

readonly SCENARIO=${1:-}

if [[ $SCENARIO == "TRACER_RELEASE_SCENARIOS" ]]; then
    for scenario in "${TRACER_RELEASE_SCENARIOS[@]}"; do pytest -p no:warnings -S $scenario ${@:2}; done

elif [[ $SCENARIO == "TRACER_ESSENTIAL_SCENARIOS" ]]; then
    for scenario in "${TRACER_ESSENTIAL_SCENARIOS[@]}"; do pytest -p no:warnings -S $scenario ${@:2}; done

elif [[ $SCENARIO == "APPSEC_SCENARIOS" ]]; then
    for scenario in "${APPSEC_SCENARIOS[@]}"; do pytest -p no:warnings -S $scenario ${@:2}; done

elif [[ $SCENARIO == "REMOTE_CONFIG_SCENARIOS" ]]; then
    for scenario in "${REMOTE_CONFIG_SCENARIOS[@]}"; do pytest -p no:warnings -S $scenario ${@:2}; done

elif [[ $SCENARIO == "TELEMETRY_SCENARIOS" ]]; then
    for scenario in "${TELEMETRY_SCENARIOS[@]}"; do pytest -p no:warnings -S $scenario ${@:2}; done

elif [[ $SCENARIO == "ONBOARDING_SCENARIOS" ]]; then
    for scenario in "${ONBOARDING_SCENARIOS[@]}"; do pytest -p no:warnings -S $scenario ${@:2}; done

elif [[ $SCENARIO == "APPSEC_IP_BLOCKING_MAXED" ]] || [[ $SCENARIO == "APPSEC_IP_BLOCKING" ]]; then
    # Those scenario has been renamed. Keep the compatibility, waiting for other CI to update.
    pytest -p no:warnings -S APPSEC_BLOCKING_FULL_DENYLIST ${@:2};

elif [[ $SCENARIO == "PARAMETRIC" ]]; then
    DEFAULT_COUNT=auto
    # FIXME: all languages should be supported
    if [ "${TEST_LIBRARY-}" ]; then
        for library in $(echo $TEST_LIBRARY | sed "s/,/ /g"); do
            # default to "1" for languages with concurrency issues
            if [[ "${library}" == "dotnet" || "${library}" == "go" ||"${library}" == "python_http" ]]; then
                DEFAULT_COUNT=1
                break
            fi
        done
    else
        # default to "1" for all languages since that includes problematic languages
        DEFAULT_COUNT=1
    fi

    # TODO: default to "auto" when dotnet is fixed
    PYTEST_WORKER_COUNT=${PYTEST_WORKER_COUNT:-$DEFAULT_COUNT}

    PYTEST_ARGS="-n $PYTEST_WORKER_COUNT"

    # FIXME: dotnet hangs when this plugin is enabled even when both "splits" and
    # "group" are set to "1" which should do effectively nothing.
    if [[ "${PYTEST_SPLITS:-}" && "${PYTEST_GROUP:-}" ]]; then
        PYTEST_ARGS="${PYTEST_ARGS} --splits $PYTEST_SPLITS --group $PYTEST_GROUP"
    fi

    eval "pytest -p no:warnings ${PYTEST_ARGS} -S PARAMETRIC ${@:2}"

elif [[ $SCENARIO =~ ^[A-Z0-9_]+$ ]]; then
    # If the first argument is a list of capital letters, then we consider it's a scenario name
    # and we add the -S option, telling pytest that's a scenario name
    #We remove the warning from the output until the protobuf bug is fixed and we can upgrade the dependencies to the latest version of pulumi
    pytest -p no:warnings -S $1 ${@:2}

else
    # otherwise, a simple proxy to pytest
    pytest -p no:warnings $@
fi
