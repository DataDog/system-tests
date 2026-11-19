#!/usr/bin/env bash
# Link the runner virtualenv baked into the SSI job image at /system-tests/venv.
# Install locally when that virtualenv is missing or was built from a different requirements.txt.

set -euo pipefail

baked="/system-tests/venv"

if [[ ! -x "${baked}/bin/pytest" || ! -f "${baked}/requirements.txt" ]]; then
  echo "No prebuilt runner virtualenv at ${baked}. Installing locally."
  rm -rf venv
  # Three attempts: a bad wheel download must not fail the job. The timeout stays at the
  # build.sh default (600s). A short timeout is what left pytest half-installed.
  SYSTEM_TEST_BUILD_ATTEMPTS=3 ./build.sh -i runner
elif [[ "$(sha256sum < "${baked}/requirements.txt")" != "$(sha256sum < requirements.txt)" ]]; then
  echo "Prebuilt runner virtualenv does not match requirements.txt. Installing locally."
  rm -rf venv
  SYSTEM_TEST_BUILD_ATTEMPTS=3 ./build.sh -i runner
else
  if [[ ! -e venv ]]; then
    ln -s "${baked}" venv
  fi
  echo "Using prebuilt runner virtualenv at ${baked}."
fi
