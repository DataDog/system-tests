#!/bin/bash

if [[ -n "${DD_INSTALLER_LIBRARY_VERSION:-}" && -z "${DD_INSTALLER_INJECTOR_VERSION:-}" ]]; then
    if [[ -n "${DD_INSTALLER_PINNED_INJECTOR_VERSION:-}" ]]; then
        DD_INSTALLER_INJECTOR_VERSION="${DD_INSTALLER_PINNED_INJECTOR_VERSION}"
    else
        AUTO_INJECT_LOCK_PATH="${AUTO_INJECT_LOCK_PATH:-auto_inject.lock}"
        if [[ ! -f "${AUTO_INJECT_LOCK_PATH}" ]]; then
            echo "ERROR: no DD_INSTALLER_PINNED_INJECTOR_VERSION provided and lock file '${AUTO_INJECT_LOCK_PATH}' not found; refusing to build with an unpinned injector" >&2
            exit 1
        fi
        DD_INSTALLER_INJECTOR_VERSION="$(tr -d '[:space:]' < "${AUTO_INJECT_LOCK_PATH}")"
        if [[ -z "${DD_INSTALLER_INJECTOR_VERSION}" ]]; then
            echo "ERROR: lock file '${AUTO_INJECT_LOCK_PATH}' is empty or invalid; refusing to build with an unpinned injector" >&2
            exit 1
        fi
    fi
    export DD_INSTALLER_INJECTOR_VERSION
    export DD_INSTALLER_REGISTRY_URL_APM_INJECT_PACKAGE='install.datadoghq.com'
    echo "Using pinned injector version from auto_inject.lock: ${DD_INSTALLER_INJECTOR_VERSION}"
elif [[ -n "${DD_INSTALLER_INJECTOR_VERSION:-}" ]]; then
    export DD_INSTALLER_REGISTRY_URL_APM_INJECT_PACKAGE='installtesting.datad0g.com'
fi
