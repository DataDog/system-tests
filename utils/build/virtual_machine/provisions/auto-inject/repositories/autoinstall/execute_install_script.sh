#!/bin/bash

# This script is needed only for this reason: https://datadoghq.atlassian.net/browse/AP-2165

# shellcheck source=/dev/null
. ./agent.lock
export DD_AGENT_MAJOR_VERSION="${DD_AGENT_VERSION%%.*}"
export DD_AGENT_MINOR_VERSION="${DD_AGENT_VERSION#*.}"
AGENT_INSTALL_SCRIPT="install_script_agent${DD_AGENT_MAJOR_VERSION}.sh"

if [ -z "${INSTALLER_URL:-}" ]; then
    INSTALLER_URL="https://dd-agent.s3.amazonaws.com/scripts/${AGENT_INSTALL_SCRIPT}"
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
      #The latest_snapshot of python tracer version is 2.x we want to use 4.x. Get from repo.
      #more details: https://datadoghq.atlassian.net/browse/APMSP-2259
      echo "DD_LANG: ${DD_LANG}"
      if [ "${DD_LANG}" == "python" ]; then
        export DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_APM_LIBRARY_PYTHON=4
      fi
else
    export DD_SITE="datadoghq.com"
      #The latest release of python tracer version is 2.x we want to use 4.x. Get from repo tags v3* and not rc*. We get the SHA of the tag.
      #more details: https://datadoghq.atlassian.net/browse/APMSP-2259
      if [ "${DD_LANG}" == "python" ]; then
        export DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_APM_LIBRARY_PYTHON=4
      fi
fi

# Environment variables for the installer
export DD_APM_INSTRUMENTATION_LIBRARIES="${DD_LANG}"

if [ -n "${DD_INSTALLER_LIBRARY_VERSION}" ]; then
   export "DD_INSTALLER_REGISTRY_URL_APM_LIBRARY_$(echo "$DD_LANG" | tr "[:lower:]" "[:upper:]")_PACKAGE"='installtesting.datad0g.com'
   export "DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_APM_LIBRARY_$(echo "$DD_LANG" | tr "[:lower:]" "[:upper:]")"="${DD_INSTALLER_LIBRARY_VERSION}"
fi

# shellcheck source=utils/build/ssi/base/installer_versions.sh
source ./installer_versions.sh

if [ "${DD_LANG}" == "js" ] && [ "${DD_env}" == "dev" ] && [ -z "${DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_APM_LIBRARY_JS}" ]; then
    # Special case for Node.js, the staging major version is 1 above the prod major (7 here)
    export DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_APM_LIBRARY_JS="7"
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

if [ -f "${AGENT_INSTALL_SCRIPT}" ]; then
    echo "*** Execute installation script from provided binaries ***"
    cp "${AGENT_INSTALL_SCRIPT}" install_script.sh
    chmod +x install_script.sh
else
    echo "Download installation script from S3"
    curl -L "$INSTALLER_URL" -o install_script.sh
fi

# shellcheck disable=SC2154
DD_REPO_URL="$DD_injection_repo_url" \
DD_APM_INSTRUMENTATION_LANGUAGES="$DD_LANG" \
bash -c "$(cat install_script.sh)"

sudo cp /tmp/datadog-installer-*.log /var/log/datadog

echo "lib-injection install done"
