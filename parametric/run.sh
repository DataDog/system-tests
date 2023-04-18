#!/usr/bin/env bash
set -eu

ARGS=$*

# FIXME: have to ignore the root conftest as it does a bunch of initialization/teardown
#        not required for the integration/shared tests.
PARENT_DIR=$(dirname $PWD)
exec python -m pytest -c $PWD/conftest.py $ARGS
