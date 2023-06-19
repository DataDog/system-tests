#!/usr/bin/env bash
set -eu

ARGS=$*

# FIXME: have to ignore the root conftest as it does a bunch of initialization/teardown
#        not required for the integration/shared tests.
cd ..
export TEST_LIBRARY=$CLIENTS_ENABLED 
echo "OJOOOOOO:::::: $(PWD)"
./build.sh -i runner
echo "OJOOOOOO:::::: $(PWD)"
./run.sh PARAMETRIC  $@
