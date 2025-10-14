#!/bin/bash

# This script is needed only for this reason: https://datadoghq.atlassian.net/browse/AP-2165

if [ -z "$INSTALLER_URL" ]; then
    INSTALLER_URL="https://dd-agent.s3.amazonaws.com/scripts/install_script_agent7.sh"
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
    export DD_INSTALLER_REGISTRY_URL='install.datad0g.com'
      #The latest_snapshot of python tracer version is 2.x we want to use 3.x. Get from repo.
      #more details: https://datadoghq.atlassian.net/browse/APMSP-2259
      echo "DD_LANG: ${DD_LANG}"
      if [ "${DD_LANG}" == "python" ]; then
        export DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_APM_LIBRARY_PYTHON=3
      fi
else 
    export DD_SITE="datadoghq.com" 
      #The latest release of python tracer version is 2.x we want to use 3.x. Get from repo tags v3* and not rc*. We get the SHA of the tag.
      #more details: https://datadoghq.atlassian.net/browse/APMSP-2259
      if [ "${DD_LANG}" == "python" ]; then
        export DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_APM_LIBRARY_PYTHON=3
      fi
fi

# Environment variables for the installer
export DD_APM_INSTRUMENTATION_LIBRARIES="${DD_LANG}"

if [ -n "${DD_INSTALLER_LIBRARY_VERSION}" ]; then
   export "DD_INSTALLER_REGISTRY_URL_APM_LIBRARY_$(echo "$DD_LANG" | tr "[:lower:]" "[:upper:]")_PACKAGE"='installtesting.datad0g.com'
   export "DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_APM_LIBRARY_$(echo "$DD_LANG" | tr "[:lower:]" "[:upper:]")"="${DD_INSTALLER_LIBRARY_VERSION}" 
fi

if [ "${DD_LANG}" == "js" ] && [ "${DD_env}" == "dev" ] && [ -z "${DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_APM_LIBRARY_JS}" ]; then
    # Special case for Node.js, the staging major version is 1 above the prod major (6 here)
    export DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_APM_LIBRARY_JS="6"
fi

if [ -n "${DD_INSTALLER_INJECTOR_VERSION}" ]; then
    export DD_INSTALLER_REGISTRY_URL_APM_INJECT_PACKAGE='installtesting.datad0g.com'
    export DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_APM_INJECT="${DD_INSTALLER_INJECTOR_VERSION}"
fi

if [ -n "${DD_INSTALLER_AGENT_VERSION}" ]; then
    export DD_INSTALLER_REGISTRY_URL_AGENT_PACKAGE='installtesting.datad0g.com'
    export DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_AGENT="${DD_INSTALLER_AGENT_VERSION}"
fi

if [ -n "${DD_INSTALLER_INSTALLER_VERSION}" ]; then
    export DD_INSTALLER_REGISTRY_URL_INSTALLER_PACKAGE='installtesting.datad0g.com'
    export DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_INSTALLER="${DD_INSTALLER_INSTALLER_VERSION}"
fi

sudo sh -c "sudo mkdir -p /etc/datadog-agent && printf \"api_key: ${DD_API_KEY}\nsite: datadoghq.com\n\" > /etc/datadog-agent/datadog.yaml"

if [ -f "install_script_agent7.sh" ]; then
    echo "*** Execute installation script from provided binaries ***"
    cp install_script_agent7.sh install_script.sh
    chmod +x install_script.sh
else
    echo "Download installation script from S3"
    curl -L $INSTALLER_URL -o install_script.sh
fi

# shellcheck disable=SC2154
DD_REPO_URL="$DD_injection_repo_url" \
DD_APM_INSTRUMENTATION_LANGUAGES="$DD_LANG" \
bash -c "$(cat install_script.sh)"

sudo cp /tmp/datadog-installer-*.log /var/log/datadog

echo "lib-injection install done"
