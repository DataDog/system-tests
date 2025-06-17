#!/usr/bin/env bash
set -e

if [ $# -lt 1 ]; then
    echo "Usage: $0 <docker-registry-base-url>"
    echo "Example: $0 235494822917.dkr.ecr.us-east-1.amazonaws.com"
    exit 1
fi

DOCKER_REGISTRY_BASE_URL="$1"

export DOCKER_IMAGE_WEBLOG_TAG=latest
export BUILDX_PLATFORMS=linux/arm64,linux/amd64
declare -A variants
variants=(["dd-lib-dotnet-init-test-app"]="dotnet"
          ["sample-app"]="nodejs"
          ["dd-lib-python-init-test-django"]="python"
          ["dd-lib-python-init-test-django-gunicorn"]="python"
          ["dd-lib-python-init-test-django-gunicorn-alpine"]="python"
          ["dd-lib-python-init-test-django-preinstalled"]="python"
          ["dd-lib-python-init-test-django-unsupported-package-force"]="python"
          ["dd-lib-python-init-test-django-uvicorn"]="python"
          ["dd-lib-python-init-test-protobuf-old"]="python"
          ["dd-lib-java-init-test-app"]="java"
          ["dd-djm-spark-test-app"]="java"
          ["dd-lib-ruby-init-test-rails"]="ruby"
          ["dd-lib-ruby-init-test-rails-bundle-deploy"]="ruby"
          ["dd-lib-ruby-init-test-rails-conflict"]="ruby"
          ["dd-lib-ruby-init-test-rails-explicit"]="ruby"
          ["dd-lib-ruby-init-test-rails-gemsrb"]="ruby"
          ["dd-lib-php-init-test-app"]="php"
          )
docker buildx create --name multiarch --driver docker-container --use

for variant in "${!variants[@]}"; do
    language="${variants[$variant]}"
    echo "Building $variant - $language";
    echo "$(pwd)"
    ./lib-injection/build/build_lib_injection_weblog.sh -w $variant -l $language --push-tag ${DOCKER_REGISTRY_BASE_URL}/system-tests/$variant:$DOCKER_IMAGE_WEBLOG_TAG --docker-platform $BUILDX_PLATFORMS
done