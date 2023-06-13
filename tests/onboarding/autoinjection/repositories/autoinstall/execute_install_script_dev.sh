#!/bin/bash

INSTALL_AGENT="true"

while [[ "$#" -gt 0 ]]; do
    case $1 in
        dotnet|java|nodejs|python) LIBRARY_LANG="$1";;
        -l|--host-inject) HOST_INSTALL="$2"; shift ;;
        -i|--container-inject) CONTAINER_INSTALL="$2"; shift ;;
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
DD_REPO_URL=datad0g.com DD_AGENT_DIST_CHANNEL=beta DD_AGENT_MAJOR_VERSION=apm DD_APM_LIBRARIES="$LIBRARY_LANG" DD_APM_HOST_INJECTION_ENABLED="$HOST_INSTALL" DD_APM_DOCKER_INJECTION_ENABLED="$CONTAINER_INSTALL" ./install_script_agent7_autoinject.sh
echo "lib-injection install done"