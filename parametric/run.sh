#!/usr/bin/env bash
set -eu

# FIXME: have to ignore the root conftest as it does a bunch of initialization/teardown
#        not required for the integration/shared tests.
PARENT_DIR=$(dirname "$PWD")

if python3.9 --version &> /dev/null; then
  readonly PYTHON=python3.9
else
  readonly PYTHON=python
fi

exec "${PYTHON}" -m pytest -c "$PWD/conftest.py" "$@"
