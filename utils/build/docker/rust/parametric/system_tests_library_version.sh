#!/bin/bash
set -eu

# Extract version from Cargo.lock
version=$(grep -A 3 'name = "datadog-opentelemetry"' ./Cargo.lock | grep -Po 'version = "\K[^"]+(?=")' | head -1)

if [ -z "$version" ]; then
    echo "Error: Could not find datadog-opentelemetry in Cargo.lock" >&2
    exit 1
fi

# Check install mode from marker file (set by install_ddtrace.sh)
# Default to "release" unless explicitly set to "dev"
if [ ! -f SYSTEM_TESTS_LIBRARY_VERSION_MODE ]; then
    echo "Warning: SYSTEM_TESTS_LIBRARY_VERSION_MODE not found, defaulting to 'release'" >&2
    mode="release"
else
    mode=$(cat SYSTEM_TESTS_LIBRARY_VERSION_MODE)
fi

if [ "$mode" = "dev" ]; then
    # Dev install: convert to dev version: increment minor, set patch to 0, add -dev suffix
    # Format: major.minor.patch -> major.(minor+1).0-dev
    base_version="${version%%[-+]*}"
    IFS='.' read -r major minor patch <<< "$base_version"
    echo "${major}.$((minor + 1)).0-dev"
else
    # Release install (default): return version as-is
    echo "$version"
fi
