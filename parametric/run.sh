#!/usr/bin/env bash
set -eu

ARGS=$*

# FIXME: have to ignore the root conftest as it does a bunch of initialization/teardown
#        not required for the integration/shared tests.
PARENT_DIR=$(dirname $PWD)
PYTEST_N=${PYTEST_N:-auto}
PYTEST_SPLITS=${PYTEST_SPLITS:-1}
PYTEST_GROUP=${PYTEST_GROUP:-1}
python -m pytest -n $PYTEST_N --splits $PYTEST_SPLITS --group $PYTEST_GROUP -c $PWD/conftest.py $ARGS
