#!/usr/bin/env bash
set -eu

ARGS=$*

# FIXME: have to ignore the root conftest as it does a bunch of initialization/teardown
#        not required for the integration/shared tests.
PARENT_DIR=$(dirname $PWD)
PYTEST_N=${PYTEST_N:-auto}

cmd="python -m pytest -n $PYTEST_N"

# FIXME: dotnet hangs when this plugin is enabled even when both splits and
# group are set to "1" which should do effectively nothing.
if [ "$PYTEST_SPLITS" ]; then
    cmd="${cmd} --splits $PYTEST_SPLITS --group ${PYTEST_GROUP=1}"
fi

cmd="$cmd -c $PWD/conftest.py $ARGS"

eval "$cmd"
