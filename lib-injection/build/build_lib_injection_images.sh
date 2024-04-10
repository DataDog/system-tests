#!/usr/bin/env bash
set -e

export DOCKER_IMAGE_WEBLOG_TAG=latest
export BUILDX_PLATFORMS=linux/arm64/v8,linux/amd64
declare -A variants
#variants=(["dd-lib-dotnet-init-test-app"]="dotnet" ["dd-lib-java-init-test-app"]="java")
variants=(["dd-lib-dotnet-init-test-app"]="dotnet" 
          ["sample-app"]="nodejs" 
          ["dd-lib-python-init-test-django"]="python"
          ["dd-lib-python-init-test-django-gunicorn"]="python"
          ["dd-lib-python-init-test-django-uvicorn"]="python"
          ["dd-lib-python-init-test-django-uvicorn"]="python"
          )
docker buildx create --name multiarch --driver docker-container --use

for variant in "${!variants[@]}"; do 
    language="${variants[$variant]}"
    echo "Building $variant - $language"; 
    echo "$(pwd)"
    cd ./lib-injection/build/docker/$language/$variant/ && APP_DOCKER_IMAGE_REPO=ghcr.io/datadog/system-tests/$variant LIBRARY_INJECTION_TEST_APP_IMAGE=ghcr.io/datadog/system-tests/$variant:$DOCKER_IMAGE_WEBLOG_TAG ./build.sh && cd ../../../../../
done