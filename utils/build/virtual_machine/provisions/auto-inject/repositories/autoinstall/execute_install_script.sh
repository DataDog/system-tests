#!/bin/bash

# This script is needed only for this reason: https://datadoghq.atlassian.net/browse/AP-2165

if [ -z "$INSTALLER_URL" ]; then
    INSTALLER_URL="https://s3.amazonaws.com/dd-agent/scripts/install_script_agent7.sh"
fi

if [ "$DD_APM_INSTRUMENTATION_ENABLED" == "docker" ]; then
    # Skip agent installation in container/docker scenarios
    export DD_NO_AGENT_INSTALL=true
fi

# shellcheck disable=SC2154
DD_REPO_URL="$DD_injection_repo_url" \
DD_APM_INSTRUMENTATION_LANGUAGES="$DD_LANG" \
bash -c "$(curl -L $INSTALLER_URL)"

echo "lib-injection install done"
