#!/usr/bin/env bash
set -eu

ARGS=$*

# FIXME: have to ignore the root conftest as it does a bunch of initialization/teardown
#        not required for the integration/shared tests.
PARENT_DIR=$(dirname $PWD)
DEFAULT_N=auto

# FIXME: all languages should be supported
if [ "${CLIENTS_ENABLED}" ]; then
    for client in $(echo $CLIENTS_ENABLED | sed "s/,/ /g"); do
        # default to "1" for languages with concurrency issues
        if [[ "${client}" == "dotnet" || "${client}" == "python_http" ]]; then
            DEFAULT_N=1
            break
        fi
    done
else
    # default to "1" for all languages since that includes problematic languages
    DEFAULT_N=1
fi

# TODO: default to "auto" when dotnet is fixed
PYTEST_N=${PYTEST_N:-$DEFAULT_N}

CMD="python -m pytest -n $PYTEST_N"

# FIXME: dotnet hangs when this plugin is enabled even when both "splits" and
# "group" are set to "1" which should do effectively nothing.
if [[ "${PYTEST_SPLITS:-}" && "${PYTEST_GROUP:-}" ]]; then
    CMD="${cmd} --splits $PYTEST_SPLITS --group $PYTEST_GROUP"
fi

CMD="$CMD -c $PWD/conftest.py $ARGS"

eval "$CMD"
