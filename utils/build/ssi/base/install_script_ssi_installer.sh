#!/bin/bash

for attempt in 1 2 3 4 5; do
    echo "[TRACE] downloading install_script_agent7.sh (attempt ${attempt})"
    if curl --fail --retry 3 --retry-delay 2 -sSL -o install_script_agent7.sh https://dd-agent.s3.amazonaws.com/scripts/install_script_agent7.sh && [ -s install_script_agent7.sh ]; then
        break
    fi
    echo "[TRACE] download failed or produced an empty file; retrying"
    rm -f install_script_agent7.sh
    sleep 2
done

if [ ! -s "install_script_agent7.sh" ]; then
    echo "[ERROR] install_script_agent7.sh is missing or empty; aborting installer setup" >&2
    exit 1
fi

DD_INSTALL_ONLY=true DD_INSTALLER=true bash ./install_script_agent7.sh
