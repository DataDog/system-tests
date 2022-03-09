#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


##########################################################################################
# This is an entrypoint file that all containers run in system-tests are funneled through.
##########################################################################################

set -eu

echo "Configuration script executed from: ${PWD}"

BASEDIR=$(dirname $0)
echo "Configuration script location: ${BASEDIR}"

if ! grep -q "#!/bin/bash" "./app.sh"; then
    echo "Please ensure you add #!/bin/bash to your ./app.sh file"
    exit 1
fi

if [ ${SYSTEMTESTS_SCENARIO:-DEFAULT} = "UDS" ]; then

    export EXPECTED_APM_SOCKET=${DD_APM_RECEIVER_SOCKET:-/var/run/datadog/apm.socket}

    echo "Setting up UDS with ${EXPECTED_APM_SOCKET}."

    if [ ${EXPECTED_APM_SOCKET} = "/var/run/datadog/apm.socket" ]; then

        echo "Attempting to use UDS default path"

        mkdir -p /var/run/datadog
        chmod -R a+rwX /var/run/datadog

        ( socat -d -d UNIX-LISTEN:${EXPECTED_APM_SOCKET},fork TCP:library_proxy:${HIDDEN_APM_PORT_OVERRIDE:-7126} > /var/log/system-tests/uds-socat.log 2>&1 ) &

    else
        echo "Using explicit UDS config"
        if [ -z ${DD_APM_RECEIVER_SOCKET+x} ]; then
            ( socat -d -d UNIX-LISTEN:${EXPECTED_APM_SOCKET},fork TCP:agent:${HIDDEN_APM_PORT_OVERRIDE} > /var/log/system-tests/uds-socat.log 2>&1 ) & 
        fi
    fi

    sleep 5

fi

./app.sh
