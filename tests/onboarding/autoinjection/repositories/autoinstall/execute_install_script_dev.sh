#!/bin/bash

#This script is needed only for this reason: https://datadoghq.atlassian.net/browse/AP-2165

INSTALL_AGENT="true"

while [[ "$#" -gt 0 ]]; do
    case $1 in
        dotnet|java|js|python|ruby) LIBRARY_LANG="$1";;
        -l|--inject-mode) DD_APM_INSTRUMENTATION_ENABLED="$2"; shift ;;
        -w|--install-agent) INSTALL_AGENT="$2"; shift ;;
        *) echo "Invalid argument: ${1:-}"; exit 1 ;;
    esac
    shift
done


curl -L https://s3.amazonaws.com/dd-agent/scripts/install_script_agent7.sh --output install_script_agent7.sh
chmod 755 install_script_agent7.sh
sed  "s/\"7\"/\"apm\"/g" install_script_agent7.sh > install_script_agent7_autoinject_temp.sh
sed  "s/-eq 7/== \"apm\"/g" install_script_agent7_autoinject_temp.sh > install_script_agent7_autoinject.sh
chmod 755 install_script_agent7_autoinject.sh

if [[ "$INSTALL_AGENT" == "true" ]]; then
    ./install_script_agent7.sh
    echo "Agent install done"
else
    export DD_NO_AGENT_INSTALL=true 
    ./install_script_agent7.sh
    echo "Skipping agent installation (Installing only datadog-signing-keys)"
fi
DD_REPO_URL=datad0g.com DD_AGENT_DIST_CHANNEL=beta DD_AGENT_MAJOR_VERSION=apm DD_APM_INSTRUMENTATION_LANGUAGES="$LIBRARY_LANG" DD_APM_INSTRUMENTATION_ENABLED="$DD_APM_INSTRUMENTATION_ENABLED" ./install_script_agent7_autoinject.sh
echo "lib-injection install done"