#!/bin/bash

# FIXME: have to use /dev/null to ignore root pytest.ini config
# FIXME: have to ignore the root conftest as it does a bunch of initialization/teardown
#        not required for the integration/shared tests.
pytest -c /dev/null -p no:$(dirname $PWD)/conftest.py .
