#!/bin/bash

ARGS=$*

# FIXME: have to use /dev/null to ignore root pytest.ini config
# FIXME: have to ignore the root conftest as it does a bunch of initialization/teardown
#        not required for the integration/shared tests.
PARENT_DIR=$(dirname $PWD)
pytest -rs -c /dev/null -p no:$(realpath $PARENT_DIR)/conftest.py . $ARGS
