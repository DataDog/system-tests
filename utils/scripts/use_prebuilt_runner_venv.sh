#!/usr/bin/env bash
# Link the runner virtualenv baked into the SSI job image at /system-tests/venv.
# Install locally when that virtualenv is missing or was built from a different requirements.txt.

set -euo pipefail

baked="/system-tests/venv"

use_prebuilt=0
if [[ -x "${baked}/bin/pytest" && -f "${baked}/requirements.txt" ]]; then
  baked_sum="$(sha256sum < "${baked}/requirements.txt")"
  checkout_sum="$(sha256sum < requirements.txt)"
  if [[ "${baked_sum}" == "${checkout_sum}" ]]; then
    use_prebuilt=1
  fi
fi

if [[ "${use_prebuilt}" -eq 1 ]]; then
  if [[ ! -e venv ]]; then
    ln -s "${baked}" venv
  fi
  echo "Using prebuilt runner virtualenv at ${baked}."
else
  echo "Prebuilt runner virtualenv is missing or does not match requirements.txt. Installing locally."
  rm -rf venv
  ./build.sh -i runner
fi
