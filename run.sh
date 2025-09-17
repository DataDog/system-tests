#!/usr/bin/env bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

set -e
set -u
set -o pipefail

function hint() {
    local program="${BASH_SOURCE[0]##*/}"
    echo "see ${program} ++help for documentation"
}

function help() {
    local program="${BASH_SOURCE[0]##*/}"
    cat <<EOS
NAME
    ${program} - run system tests test suite

SYNOPSIS
    ${program} +h

    ${program} [+d] [+S scenario...] [+G scenario group...] [++] [pytest arguments]

    ${program} [+d] SCENARIO [pytest arguments]

    ${program} [+d] GROUPED_SCENARIOS [pytest arguments]

OPTIONS
    Using option flags is the recommended way to use ${program}.

    +v, ++verbose
      Increase verbosity.

    +y, ++dry
      Do a dry run, i.e pretend to run but do nothing, instead outputting
      commands that would be run.

    +d, ++docker
      Run tests in a Docker container. The runner image must be built beforehand.

    +S, ++scenario SCENARIO
      Add scenario SCENARIO to the list of scenarios to run. Case-insensitive.

    +G, ++scenario-group GROUPED_SCENARIOS
      Add all scenarios in GROUPED_SCENARIOS group to the list of scenarios to
      run. Case insensitive.

    +l, ++library LIBRARY
      Inform test suite that test pertains to LIBRARY.

    ++
      Ignore flags after this separator. All subsequent arguments are passed
      as-is to pytest.

POSITIONAL ARGUMENTS
    Using positional arguments is deprecated in favor of options (see OPTIONS
    above). Subsequent flags are ignored and arguments passed as-is to pytest.

    SCENARIO
      Run scenario SCENARIO. Case sensitive, must be uppercase.

    GROUPED_SCENARIOS
      Run all scenarios in GROUPED_SCENARIOS group. Case sensitive, must be
      uppercase, must end with _SCENARIOS.

HOMEPAGE
    <https://github.com/Datadog/system-tests>

    Please report bugs and feature requests in the issue tracker. Please do
    your best to provide a reproducible test case for bugs.
EOS
}

function error() {
    echo "error:" "$@" 1>&2
}

function warn() {
    echo "warn:" "$@" 1>&2
}

function die() {
    local rc=1

    if [[ $1 =~ ^-?[0-9]+$ ]]; then
        rc="$1"
        shift
    fi

    error "$@"
    exit "${rc}"
}

function lookup_scenario_group() {
    local group="$1"
    local mode="$2"

    local python=()

    case "${mode}" in
        'docker')
            python+=(
              docker run
              --rm -i
              system_tests/runner
              venv/bin/python
            )
            ;;
        'direct')
            python+=(python)
            ;;
        *)
            die "unsupported run mode: ${mode}"
            ;;
    esac

    python+=(utils/scripts/get-scenarios-from-group.py)

    PYTHONPATH=. "${python[@]}" "${group}"
}

function upcase() {
    tr '[:lower:]' '[:upper:]'
}

function downcase() {
    tr '[:upper:]' '[:lower:]'
}

function is_using_nix() {
    [[ -n "${IN_NIX_SHELL:-}" ]]
}

function activate_venv() {
    # shellcheck disable=SC1091
    source venv/bin/activate
}

function ensure_network() {
    local network_name

    # limited support of docker mode: it can't control test targets, so going for the most common use case
    # reminder : this mode is unofficial and not supported (for the exact reason it can't control test targets...)
    network_name="system-tests-ipv4"

    if docker network ls | grep -q "${network_name}"; then
        : # network exists
    else
        docker network create "${network_name}"
    fi
}

function run_scenario() {
    local dry="$1"
    shift
    local mode="$1"
    shift
    local scenario="$1"
    shift
    local pytest_args=("$@")

    local cmd=()

    if [[ "${dry}" -gt 0 ]]; then
        cmd+=(echo)
    fi

    case "${mode}" in
        'docker')
            # infer log dir from scenario
            local log_dir

            # default scenario does not follow the convention
            if [[ "${scenario}" == 'DEFAULT' ]]; then
                log_dir='logs'
            else
                # downcase via ${scenario,,} is unsupported on bash 3.x
                log_dir="logs_$(echo "${scenario}" | downcase )"
            fi

            cmd+=(
              docker run
              --network system-tests-ipv4
              --rm -i
            )
            if [ -t 1 ]; then
                cmd+=(-t)
            fi
            if [[ -n "${DD_API_KEY:-}" ]]; then
              cmd+=(
                -e DD_API_KEY="${DD_API_KEY}"
              )
            fi
            if [[ -f .env ]]; then
              cmd+=(
                -v "${PWD}"/.env:/app/.env
              )
            fi
            cmd+=(
              -v /var/run/docker.sock:/var/run/docker.sock
              -v "${PWD}/${log_dir}":"/app/${log_dir}"
              -e SYSTEM_TESTS_PROXY_HOST=proxy
              -e SYSTEM_TESTS_WEBLOG_HOST=weblog
              -e SYSTEM_TESTS_WEBLOG_PORT=7777
              -e SYSTEM_TESTS_WEBLOG_GRPC_PORT=7778
              -e SYSTEM_TESTS_HOST_PROJECT_DIR="${PWD}"
              --name system-tests-runner
              system_tests/runner
              venv/bin/pytest
            )
            ;;
        'direct')
            cmd+=(pytest)
            ;;
        *)
            die "unsupported run mode: ${mode}"
            ;;
    esac

    cmd+=(
        -S "${scenario}"
        "${pytest_args[@]}"
    )

    "${cmd[@]}"
}

function main() {

    local docker="${DOCKER_MODE:-0}"
    local verbosity=0
    local dry=0
    local scenario_args=()
    local libraries=()
    local pytest_args=()
    local pytest_numprocesses='auto'

    ## handle environment variables

    # split TEST_LIBRARY on ','
    IFS=',' read -r -a libraries <<< "${TEST_LIBRARY:-}"

    ## parse command arguments

    # parse flags
    while [[ "$#" -gt 0 ]]; do
        case "$1" in
            +h|++help)
                help
                exit
                ;;
            +v|++verbose)
                verbosity=$(( verbosity + 1 ))
                ;;
            +y|++dry)
                dry=1
                ;;
            +d|++docker)
                docker=1
                ;;
            +G|++scenario-group)
                if [[ "$#" -eq 1 ]]; then
                  error "missing argument value for: $1"
                  help
                  exit 64
                fi
                # upcase via ${2^^} is unsupported on bash 3.x
                scenario_args+=("$(echo "$2" | upcase)")
                shift
                ;;
            +S|++scenario|-S|--scenario)
                # this also catches '-S' even though it's a pytest flag because
                # there may be special treatment for specific scenarios
                if [[ "$#" -eq 1 ]]; then
                  error "missing argument value for: $1"
                  hint
                  exit 64
                fi
                # upcase via ${2^^} is unsupported on bash 3.x
                scenario_args+=("$(echo "$2" | upcase)")
                shift
                ;;
            +l|++library)
                if [[ "$#" -eq 1 ]]; then
                  error "missing argument value for: $1"
                  hint
                  exit 64
                fi
                libraries+=("$2")
                shift
                ;;
            ++)
                # ignore and stop flag processing to force remainder to be captured as is
                shift
                break
                ;;
            +*)
                # unknown flag: be helpful
                error "unknown flag: $1"
                hint
                exit 64
                ;;
            *)
                # handle positional arguments
                if [[ "$1" =~ ^[A-Z0-9_]+$ ]]; then
                    scenario_args+=("$1")
                else
                    # pass any unmatched arguments to pytest
                    pytest_args+=("$1")
                fi
                ;;
        esac
        shift
    done

    # capture remainder of arguments to pass as-is for pytest
    pytest_args+=("$@")

    ## prepare commands

    # set run mode
    if [[ "${docker}" == 1 ]]; then
        run_mode='docker'
    else
        run_mode='direct'
    fi

    # check if runner is installed and up to date
    if [[ "${run_mode}" == "direct" ]] && ! is_using_nix && ! diff requirements.txt venv/requirements.txt; then
        ./build.sh -i runner
    fi

    # ensure environment
    if [[ "${run_mode}" == "docker" ]] || is_using_nix; then
        : # no venv needed
    else
        activate_venv
    fi

    local python_version
    python_version="$(python -V 2>&1 | sed -E 's/Python ([0-9]+)\.([0-9]+).*/\1\2/')"
    if [[ "$python_version" -lt "312" ]]; then
        echo "⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️⚠️⚠️️️️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️⚠️⚠️️️️⚠️⚠️⚠️️️️⚠️⚠️⚠️️️️⚠️⚠️⚠️️️️⚠️⚠️⚠️️️️⚠️"
        echo "DEPRECRATION WARNING: you're using python ${python_version} to run system-tests."
        echo "This won't be supported soon. Please install python3.12, then run:"
        echo "> rm -rf venv && ./build.sh -i runner"
        echo "⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️⚠️⚠️️️️"
    fi

    # process scenario list
    local scenarios=()

    # expand scenario groups
    # bash 3.x does not support mapfile, dance around with tr and IFS
    # bash 3.x considers ${arr[@}} undefined if empty
    if [[ ${#scenario_args[@]} -gt 0 ]]; then
        for i in "${scenario_args[@]}"; do
            if [[ "${i}" =~ [A-Z0-9_]+_SCENARIOS$ ]]; then
                    # bash 3.x does not support mapfile, dance around with tr and IFS
                    IFS=',' read -r -a group <<< "$(lookup_scenario_group "${i}" "${run_mode}" | tr '\n' ',')"
                    scenarios+=("${group[@]}")
            else
                    scenarios+=("${i}")
            fi
        done
    fi

    # when no scenario is provided, use a nice default
    if [[ "${#scenarios[@]}" -lt 1 ]]; then
        scenarios+=('DEFAULT')
    fi

    # backward compatibility with scenarios that have been removed/renamed
    # TODO: remove once all CIs have been updated
    for i in "${!scenarios[@]}"; do
        case "${scenarios["${i}"]}" in
            APPSEC_IP_BLOCKING_MAXED|APPSEC_IP_BLOCKING)
                scenarios+=(APPSEC_BLOCKING_FULL_DENYLIST)
                unset "scenarios[${i}]"
                ;;

            LIBRARY_CONF_CUSTOM_HEADERS_SHORT|LIBRARY_CONF_CUSTOM_HEADERS_LONG)
                scenarios+=(LIBRARY_CONF_CUSTOM_HEADER_TAGS)
                unset "scenarios[${i}]"
                ;;

            APPSEC_DISABLED)
                scenarios+=(EVERYTHING_DISABLED)
                unset "scenarios[${i}]"
                ;;

            APPSEC_STANDALONE_V2)
                scenarios+=(APPSEC_STANDALONE)
                unset "scenarios[${i}]"
                ;;

            TELEMETRY_APP_STARTED_CONFIG_CHAINING)
                scenarios+=(TELEMETRY_ENHANCED_CONFIG_REPORTING)
                unset "scenarios[${i}]"
                ;;

            IAST_STANDALONE_V2)
                scenarios+=(IAST_STANDALONE)
                unset "scenarios[${i}]"
                ;;

            SCA_STANDALONE_V2)
                scenarios+=(SCA_STANDALONE)
                unset "scenarios[${i}]"
                ;;

            APM_TRACING_E2E)
                unset "scenarios[${i}]"
                ;;
        esac
    done

    # TODO: remove duplicates

    # TODO: upgrade the dependencies to the latest version of pulumi once the protobuf bug is fixed
    # In the meantime remove the warning from the output
    pytest_args+=( '-p' 'no:warnings' )

    # evaluate max pytest number of process
    for scenario in "${scenarios[@]}"; do
        if [[ "${scenario}" != "PARAMETRIC" ]]; then
            pytest_numprocesses=1
        fi
    done

    if [[ "${#libraries[@]}" -gt 0 ]]; then
      for library in "${libraries[@]}"; do
          if [ "${library}" = "dotnet" ]; then
            pytest_numprocesses=1
          fi
      done
    fi

    # evaluate max pytest number of process for K8s_lib_injection
    for scenario in "${scenarios[@]}"; do
        if [[ "${scenario}" == K8S_LIBRARY_INJECTION_* ]]; then
            pytest_numprocesses=$(nproc)
        fi
    done

    case "${pytest_numprocesses}" in
        0|1)
            ;;
        *)
            pytest_args+=( '-n' "${pytest_numprocesses}" )
            ;;
    esac

    ## run tests
    if [[ "${verbosity}" -gt 0 ]]; then
        echo "plan:"
        echo "  mode: ${run_mode}"
        echo "  dry run: ${dry}"
        echo "  scenarios:"
        for scenario in "${scenarios[@]}"; do
            echo "    - ${scenario}"
        done
    fi

    if [[ "${run_mode}" == "docker" ]]; then
        ensure_network >/dev/null
    fi

    for scenario in "${scenarios[@]}"; do
        #TODO SCENARIO WAS REMOVED, TEMPORARY FIX TILL CI IS FIXED
        if [[ "${scenario}" == DEBUGGER_METHOD_PROBES_SNAPSHOT ]]; then
            echo "${scenario} was removed, skipping."
            continue
        fi
        if [[ "${scenario}" == DEBUGGER_LINE_PROBES_SNAPSHOT ]]; then
            echo "${scenario} was removed, skipping."
            continue
        fi
        if [[ "${scenario}" == DEBUGGER_MIX_LOG_PROBE ]]; then
            echo "${scenario} was removed, skipping."
            continue
        fi
        if [[ "${scenario}" == REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING_NOCACHE ]]; then
            echo "${scenario} was removed, skipping."
            continue
        fi
        ####

        run_scenario "${dry}" "${run_mode}" "${scenario}" "${pytest_args[@]}"
    done
}

if [[ "$0" == "${BASH_SOURCE[0]}" ]]; then
    main "$@"
fi
