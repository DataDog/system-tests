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

    # formatted perl code with -e for readabiliy
    # shellcheck disable=SC2016
    cat < scenario_groups.yml \
        | env GROUP="${group}" perl -0777 \
               -e '    use v5.30;                                          ' \
               -e '    use YAML qw[ Load ];                                ' \
               -e '                                                        ' \
               -e '    # get group                                         ' \
               -e '    my $group = $ENV{"GROUP"};                          ' \
               -e '                                                        ' \
               -e '    # parse yaml by surlping (0777) from stdin          ' \
               -e '    my $yaml = Load(<>);                                ' \
               -e '                                                        ' \
               -e '    # dereference ref to hash                           ' \
               -e '    my %groups = %{ $yaml };                            ' \
               -e '                                                        ' \
               -e '    # test if key exists                                ' \
               -e '    if (! exists $groups{$group}) {                     ' \
               -e '      print STDERR "error: group ${group} not found\n"; ' \
               -e '      exit 1                                            ' \
               -e '    }                                                   ' \
               -e '                                                        ' \
               -e '    # get list, dereference ref to array                ' \
               -e '    my @scenarios = @{ %groups{$group} };               ' \
               -e '                                                        ' \
               -e '    foreach my $e (@scenarios) {                        ' \
               -e '      if (ref $e eq "ARRAY") {                          ' \
               -e '        # flatten second level array                    ' \
               -e '        foreach my $f (@{ $e }) {                       ' \
               -e '           print "${f}\n";                              ' \
               -e '        }                                               ' \
               -e '      } else { # string                                 ' \
               -e '        print "${e}\n";                                 ' \
               -e '      }                                                 ' \
               -e '    }                                                   '
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
              --network system-tests_default
              --rm -it
              -v "${PWD}"/.env:/app/.env
              -v /var/run/docker.sock:/var/run/docker.sock
              -v "${PWD}/${log_dir}":"/app/${log_dir}"
              -e SYSTEM_TESTS_WEBLOG_HOST=weblog
              -e SYSTEM_TESTS_WEBLOG_PORT=7777
              -e SYSTEM_TESTS_WEBLOG_GRPC_PORT=7778
              -e SYSTEM_TESTS_HOST_PROJECT_DIR="${PWD}"
              --name system-tests-runner
              system_tests/runner
              venv/bin/pytest -S "${scenario}" "${pytest_args[@]}"
            )
            ;;
        'direct')
            cmd+=(pytest -S "${scenario}" "${pytest_args[@]}")
            ;;
        *)
            die "unsupported run mode: ${mode}"
            ;;
    esac

    "${cmd[@]}"
}

function main() {
    local docker="${DOCKER_MODE:-0}"
    local verbosity=0
    local dry=0
    local scenarios=()
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
                mapfile -t group <<< "$(lookup_scenario_group "$(echo "$2" | upcase)")"
                scenarios+=("${group[@]}")
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
                scenarios+=("$(echo "$2" | upcase)")
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
                if [[ "$1" =~ [A-Z0-9_]+_SCENARIOS$ ]]; then
                    mapfile -t group <<< "$(lookup_scenario_group "$1")"
                    scenarios+=("${group[@]}")
                elif [[ "$1" =~ ^[A-Z0-9_]+$ ]]; then
                    scenarios+=("$1")
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
          case "${library}" in
              dotnet|go|python_http)
                  pytest_numprocesses=1
                  ;;
          esac
      done
    fi

    case "${pytest_numprocesses}" in
        0|1)
            ;;
        *)
            pytest_args+=( '-n' "${pytest_numprocesses}" )
            ;;
    esac

    ## run tests

    if [[ "${docker}" == 1 ]]; then
        run_mode='docker'
    else
        run_mode='direct'

        # ensure environment
        if ! is_using_nix; then
            activate_venv
        fi
    fi

    if [[ "${verbosity}" -gt 0 ]]; then
        echo "plan:"
        echo "  mode: ${run_mode}"
        echo "  dry run: ${dry}"
        echo "  scenarios:"
        for scenario in "${scenarios[@]}"; do
            echo "    - ${scenario}"
        done
    fi

    for scenario in "${scenarios[@]}"; do
        run_scenario "${dry}" "${run_mode}" "${scenario}" "${pytest_args[@]}"
    done
}

if [[ "$0" == "${BASH_SOURCE[0]}" ]]; then
    main "$@"
fi
