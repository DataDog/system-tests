#!/bin/bash

#We want latest releases or the latest snapshot
if [ "${SSI_ENV}" == "dev" ]; then
    # To force the installer to pull from dev repositories -- agent config is set manually to datadoghq.com
    export DD_SITE="datad0g.com"
    export DD_INSTALLER_REGISTRY_URL='install.datad0g.com'
    export DD_injection_repo_url='datad0g.com'
    #The latest_snapshot of python tracer version is 2.x we want to use 3.x. Get from repo.
    #more details: https://datadoghq.atlassian.net/browse/APMSP-2259
    echo "DD_LANG: ${DD_LANG}"
    if [ "${DD_LANG}" == "python" ]; then
    # shellcheck disable=SC2155
    export DD_INSTALLER_LIBRARY_VERSION=$(TMP=$(mktemp -d); git -C "$TMP" init -q && git -C "$TMP" fetch -q --depth=2 https://github.com/Datadog/dd-trace-py.git main && (git -C "$TMP" rev-parse FETCH_HEAD^ || git -C "$TMP" rev-parse FETCH_HEAD); rm -rf "$TMP")
    fi

else
    export DD_SITE="datadoghq.com"
    export DD_injection_repo_url='datadoghq.com'
    #The latest release of python tracer version is 2.x we want to use 3.x. Get from repo tags v3* and not rc*. We get the SHA of the tag.
    #more details: https://datadoghq.atlassian.net/browse/APMSP-2259
    if [ "${DD_LANG}" == "python" ]; then
        # shellcheck disable=SC2155
        export DD_INSTALLER_LIBRARY_VERSION=$(REPO=https://github.com/Datadog/dd-trace-py.git; TAG=$(git ls-remote --tags --refs "$REPO" 'v3*' | cut -f2 | sed 's#refs/tags/##' | grep -Eiv '(-?rc[0-9]*$)' | sort -V | tail -1); [ -z "$TAG" ] && { echo "No stable v3* tags found" >&2; exit 1; }; SHA=$(git ls-remote --tags "$REPO" "refs/tags/$TAG^{}" | cut -f1); [ -n "$SHA" ] || SHA=$(git ls-remote --tags "$REPO" "refs/tags/$TAG" | cut -f1); echo "$SHA")
    fi
fi

#We want specfic library version (to run on tracers pipelines)
if [ -n "${DD_INSTALLER_LIBRARY_VERSION}" ]; then
    export "DD_INSTALLER_REGISTRY_URL_APM_LIBRARY_$(echo "$DD_LANG" | tr "[:lower:]" "[:upper:]")_PACKAGE"='installtesting.datad0g.com'
    export "DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_APM_LIBRARY_$(echo "$DD_LANG" | tr "[:lower:]" "[:upper:]")"="${DD_INSTALLER_LIBRARY_VERSION}"
fi

if [ "${DD_LANG}" == "js" ] && [ "${SSI_ENV}" == "dev" ] && [ -z "${DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_APM_LIBRARY_JS}" ]; then
    # Special case for Node.js, the staging major version is 1 above the prod major (6 here)
    export DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_APM_LIBRARY_JS="6"
fi

#We want specfic injector version (to run on auto_inject pipelines)
if [ -n "${DD_INSTALLER_INJECTOR_VERSION}" ]; then
    export DD_INSTALLER_REGISTRY_URL_APM_INJECT_PACKAGE='installtesting.datad0g.com'
    export DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_APM_INJECT="${DD_INSTALLER_INJECTOR_VERSION}"
fi

DD_REPO_URL=${DD_injection_repo_url}  DD_INSTALL_ONLY=true DD_APM_INSTRUMENTATION_ENABLED=host  bash -c "$(curl -L https://s3.amazonaws.com/dd-agent/scripts/install_script_agent7.sh)"

if [ -f /etc/debian_version ] || [ "$DISTRIBUTION" == "Debian" ] || [ "$DISTRIBUTION" == "Ubuntu" ]; then
    OS="Debian"
elif [ -f /etc/redhat-release ] || [ "$DISTRIBUTION" == "RedHat" ] || [ "$DISTRIBUTION" == "CentOS" ] || [ "$DISTRIBUTION" == "Amazon" ] || [ "$DISTRIBUTION" == "Rocky" ] || [ "$DISTRIBUTION" == "AlmaLinux" ]; then
    OS="RedHat"
# Some newer distros like Amazon may not have a redhat-release file
elif [ -f /etc/system-release ] || [ "$DISTRIBUTION" == "Amazon" ]; then
    OS="RedHat"
# Arista is based off of Fedora14/18 but do not have /etc/redhat-release
elif [ -f /etc/Eos-release ] || [ "$DISTRIBUTION" == "Arista" ]; then
    OS="RedHat"
# openSUSE and SUSE use /etc/SuSE-release or /etc/os-release
elif [ -f /etc/SuSE-release ] || [ "$DISTRIBUTION" == "SUSE" ] || [ "$DISTRIBUTION" == "openSUSE" ]; then
    OS="SUSE"
fi

# Not needed since we use the test agent, this only makes the image bigger
if [ "$OS" == "RedHat" ]; then
    yum erase --assumeyes datadog-agent
elif [ "$OS" == "Debian" ]; then
    apt-get remove --yes datadog-agent
fi
