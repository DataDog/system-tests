#!/usr/bin/env bash
set -eu

ARGS=$*

# FIXME: have to ignore the root conftest as it does a bunch of initialization/teardown
#        not required for the integration/shared tests.
echo "Legacy way to run parametric test. Please use ./run.sh PARAMETRIC"
cd ..
export TEST_LIBRARY=$CLIENTS_ENABLED
./build.sh -i runner
./run.sh PARAMETRIC  $@
