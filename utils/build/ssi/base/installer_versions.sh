#!/bin/bash

if [[ -n "${DD_INSTALLER_LIBRARY_VERSION:-}" && -z "${DD_INSTALLER_INJECTOR_VERSION:-}" ]]; then
    if [[ -n "${DD_INSTALLER_PINNED_INJECTOR_VERSION:-}" ]]; then
        DD_INSTALLER_INJECTOR_VERSION="${DD_INSTALLER_PINNED_INJECTOR_VERSION}"
    else
        DD_INSTALLER_INJECTOR_VERSION="$(tr -d '[:space:]' < "${AUTO_INJECT_LOCK_PATH:-auto_inject.lock}")"
    fi
    export DD_INSTALLER_INJECTOR_VERSION
    echo "Using pinned injector version from auto_inject.lock: ${DD_INSTALLER_INJECTOR_VERSION}"
fi
