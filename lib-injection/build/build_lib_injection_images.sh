#!/usr/bin/env bash
set -e

export DOCKER_IMAGE_WEBLOG_TAG=latest

declare -A variants
variants=(["dd-lib-dotnet-init-test-app"]="dotnet" ["dd-lib-java-init-test-app"]="java")

for variant in "${!variants[@]}"; do 
    language="${variants[$variant]}"
    echo "Building $variant - $language"; 
    echo "$(pwd)"
    cd ./lib-injection/build/docker/$language/$variant/ && APP_DOCKER_IMAGE_REPO=ghcr.io/datadog/system-tests/$variant LIBRARY_INJECTION_TEST_APP_IMAGE=ghcr.io/datadog/system-tests/$variant:$DOCKER_IMAGE_WEBLOG_TAG ./build.sh && cd ../../../../../
done