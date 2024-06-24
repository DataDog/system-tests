#!/usr/bin/env bash
set -e

export DOCKER_IMAGE_WEBLOG_TAG=latest
export BUILDX_PLATFORMS=linux/arm64/v8,linux/amd64
declare -A variants
variants=(["dd-lib-dotnet-init-test-app"]="dotnet"
    ["sample-app"]="nodejs"
    ["dd-lib-python-init-test-django"]="python"
    ["dd-lib-python-init-test-django-gunicorn"]="python"
    ["dd-lib-python-init-test-django-uvicorn"]="python"
    ["dd-lib-ruby-init-test-rails"]="ruby"
    ["dd-lib-ruby-init-test-rails-bundle-deploy"]="ruby"
    ["dd-lib-ruby-init-test-rails-conflict"]="ruby"
    ["dd-lib-ruby-init-test-rails-explicit"]="ruby"
    ["dd-lib-ruby-init-test-rails-gemsrb"]="ruby"
    ["dd-lib-java-init-test-app"]="java"
)
docker buildx create --name multiarch --driver docker-container --use

for variant in "${!variants[@]}"; do
    language="${variants[$variant]}"
    echo "Building $variant - $language"
    echo "$(pwd)"
    ./lib-injection/build/build_lib_injection_weblog.sh -w $variant -l $language --push-tag ghcr.io/datadog/system-tests/$variant:$DOCKER_IMAGE_WEBLOG_TAG

done
