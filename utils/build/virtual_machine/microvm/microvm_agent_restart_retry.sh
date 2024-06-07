#!/bin/bash

#This script will only run whebn the provider is KRUNVM
#Krunvm incorporates a very interesting feature: virtio-vsock (specialized for TSI, Transparent Socket Impersonation).
#This feature allows the guest to communicate with the host without the need for a network interface, but some programs doesn't support it very well.
#For example, the agent doesn't support it, so we need to restart the agent to make it work.
#Also the krunvm machines don't have systemd, so we need to use a custom service command to start, stop and restart the agent. We mock systemctl command to make it work.


#MicroVm: The agent does not  start. Dirty way: retry until it works. :-(
RESPONSE=$(cat /usr/bin/systemctl)
if [[ $(echo "$RESPONSE" | grep "microvm") ]]; then
    TIMEOUT=90
    while true; do
    RESPONSE_PROCESS=$(service datadog-agent-process status)
    RESPONSE_TRACE=$(service datadog-agent-trace status)
    RESPONSE_AGENT=$(service datadog-agent status)
    if [[ $(echo "$RESPONSE_PROCESS" | grep "active (running)") ]] && [[ $(echo "$RESPONSE_TRACE" | grep "active (running)") ]] && [[ $(echo "$RESPONSE_AGENT" | grep "active (running)") ]]; then
        echo "Agent running OK"
        break
    else
        echo "Agent not running"
    fi

    if [[ $SECONDS -ge $TIMEOUT ]]; then
        echo "Agent doesn't start in $TIMEOUT seconds"
        break
    fi
    echo "start agent again..."
    sleep 2
    service datadog-agent-process stop
    service datadog-agent-trace stop
    service datadog-agent stop
    sleep 2
    service datadog-agent start
    service datadog-agent-process start
    service datadog-agent-trace start
    sleep 15
    service datadog-agent status
    service datadog-agent-process status
    service datadog-agent-trace status
    done
fi