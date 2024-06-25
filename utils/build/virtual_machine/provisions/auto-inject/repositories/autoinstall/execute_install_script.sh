#!/bin/bash

#This script is needed only for this reason: https://datadoghq.atlassian.net/browse/AP-2165

if [ -z "$INSTALLER_URL" ]; then
    INSTALLER_URL="https://s3.amazonaws.com/dd-agent/scripts/install_script_agent7.sh"
fi

curl -L "$INSTALLER_URL" --output install_script_agent7.sh
chmod 755 install_script_agent7.sh
# shellcheck disable=SC2154
sed  "s/\"7\"/\"$DD_injection_major_version\"/g" install_script_agent7.sh > install_script_agent7_autoinject_temp.sh
sed  "s/-eq 7/== \"$DD_injection_major_version\"/g" install_script_agent7_autoinject_temp.sh > install_script_agent7_autoinject.sh
chmod 755 install_script_agent7_autoinject.sh

if [ "$1" == "docker" ]; then
    echo "Skipping agent installation in container/docker scenario (Installing only datadog-signing-keys)"
    # shellcheck disable=SC2154
    DD_SITE=$DD_injection_repo_url DD_NO_AGENT_INSTALL=true ./install_script_agent7.sh
fi
# shellcheck disable=SC2154
DD_SITE=$DD_injection_repo_url  \
DD_REPO_URL=$DD_injection_repo_url \
DD_AGENT_DIST_CHANNEL=$DD_injection_dist_channel \
DD_AGENT_MAJOR_VERSION=$DD_injection_major_version \
DD_APM_INSTRUMENTATION_LANGUAGES="$DD_LANG" \
DD_APM_INSTRUMENTATION_ENABLED="$DD_APM_INSTRUMENTATION_ENABLED" \
DD_PROFILING_ENABLED="$DD_PROFILING_ENABLED" \
./install_script_agent7_autoinject.sh

echo "lib-injection install done"
