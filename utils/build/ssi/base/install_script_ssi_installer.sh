#!/bin/bash

# shellcheck source=utils/build/ssi/base/download_with_retry.sh
source ./download_with_retry.sh

download_with_retry https://dd-agent.s3.amazonaws.com/scripts/install_script_agent7.sh || exit 1

if ! run_with_retry \
    "Datadog Agent installer" \
    3 \
    5 \
    env \
    DD_INSTALL_ONLY=true \
    DD_INSTALLER=true \
    bash ./install_script_agent7.sh; then
    echo "[ERROR] aborting SSI install after Datadog Agent installer failure" >&2
    exit 1
fi
