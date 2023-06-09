#!/bin/bash
LANG=$1
curl -L https://s3.amazonaws.com/dd-agent/scripts/install_script_agent7.sh --output install_script_agent7.sh
chmod 755 install_script_agent7.sh
sed  "s/\"7\"/\"apm\"/g" install_script_agent7.sh > install_script_agent7_autoinject.sh
chmod 755 install_script_agent7_autoinject.sh
./install_script_agent7.sh
echo "Agent install done"
DD_REPO_URL=datad0g.com DD_AGENT_DIST_CHANNEL=beta DD_AGENT_MAJOR_VERSION=apm DD_APM_LIBRARIES="$LANG" DD_APM_HOST_INJECTION_ENABLED=true ./install_script_agent7_autoinject.sh
echo "lib-injection install done"