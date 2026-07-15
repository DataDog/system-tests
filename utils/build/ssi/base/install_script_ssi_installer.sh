#!/bin/bash

# shellcheck source=utils/build/ssi/base/download_with_retry.sh
source ./download_with_retry.sh

download_with_retry https://dd-agent.s3.amazonaws.com/scripts/install_script_agent7.sh || exit 1

DD_INSTALL_ONLY=true DD_INSTALLER=true bash ./install_script_agent7.sh
