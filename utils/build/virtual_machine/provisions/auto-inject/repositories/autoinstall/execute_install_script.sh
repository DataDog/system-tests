#!/bin/bash

# This script is needed only for this reason: https://datadoghq.atlassian.net/browse/AP-2165

if [ -z "$INSTALLER_URL" ]; then
    INSTALLER_URL="https://install.datadoghq.com/scripts/install_script_agent7.sh"
fi

if [ "$DD_APM_INSTRUMENTATION_ENABLED" == "docker" ]; then
    # Skip agent installation in container/docker scenarios
    export DD_NO_AGENT_INSTALL=true
fi

# Installer env vars
# shellcheck disable=SC2154
if [ "${DD_env}" == "dev" ]; then
    # To force the installer to pull from dev repositories -- agent config is set manually to datadoghq.com
    export DD_SITE="datad0g.com"
    export DD_INSTALLER_REGISTRY_URL='669783387624.dkr.ecr.us-east-1.amazonaws.com/dockerhub/datadog'
    export DD_INSTALLER_REGISTRY_AUTH='ecr'
else 
    export DD_SITE="datadoghq.com" 
fi

# Environment variables for the installer
export DD_APM_INSTRUMENTATION_LIBRARIES="${DD_LANG}"
export DD_INSTALLER_DEFAULT_PKG_INSTALL_DATADOG_AGENT=true

if [ -n "${DD_INSTALLER_LIBRARY_VERSION}" ]; then
   export "DD_INSTALLER_REGISTRY_AUTH_APM_LIBRARY_$(echo "$DD_LANG" | tr "[:lower:]" "[:upper:]")_PACKAGE"='ecr'
   export "DD_INSTALLER_REGISTRY_URL_APM_LIBRARY_$(echo "$DD_LANG" | tr "[:lower:]" "[:upper:]")_PACKAGE"='669783387624.dkr.ecr.us-east-1.amazonaws.com'
   export "DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_APM_LIBRARY_$(echo "$DD_LANG" | tr "[:lower:]" "[:upper:]")"="${DD_INSTALLER_LIBRARY_VERSION}" 
fi

if [ -n "${DD_INSTALLER_INJECTOR_VERSION}" ]; then
    export DD_INSTALLER_REGISTRY_AUTH_APM_INJECT_PACKAGE='ecr'
    export DD_INSTALLER_REGISTRY_URL_APM_INJECT_PACKAGE='669783387624.dkr.ecr.us-east-1.amazonaws.com'
    export DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_APM_INJECT="${DD_INSTALLER_INJECTOR_VERSION}"
fi

if [ -n "${DD_INSTALLER_AGENT_VERSION}" ]; then
    export DD_INSTALLER_REGISTRY_AUTH_AGENT_PACKAGE='ecr'
    export DD_INSTALLER_REGISTRY_URL_AGENT_PACKAGE='669783387624.dkr.ecr.us-east-1.amazonaws.com'
    export DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_AGENT="${DD_INSTALLER_AGENT_VERSION}"
fi

if [ -n "${DD_INSTALLER_INSTALLER_VERSION}" ]; then
    export DD_INSTALLER_REGISTRY_AUTH_INSTALLER_PACKAGE='ecr'
    export DD_INSTALLER_REGISTRY_URL_INSTALLER_PACKAGE='669783387624.dkr.ecr.us-east-1.amazonaws.com'
    export DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_INSTALLER="${DD_INSTALLER_INSTALLER_VERSION}"
fi

sudo sh -c "sudo mkdir -p /etc/datadog-agent && printf \"api_key: ${DD_API_KEY}\nsite: datadoghq.com\n\" > /etc/datadog-agent/datadog.yaml"

# shellcheck disable=SC2154
DD_REPO_URL="$DD_injection_repo_url" \
DD_APM_INSTRUMENTATION_LANGUAGES="$DD_LANG" \
bash -c "$(curl -L "$INSTALLER_URL")"

sudo cp /tmp/datadog-installer-*.log /var/log/datadog

echo "lib-injection install done"
