#!/usr/bin/env bash

# buddies are weblog app in another lang
# they are used in the CROSSED_TRACING_LIBRARIES scenario, where we can tests data propagation between different languages

set -eu

build_buddy() {
    local dockerfile="$1"
    local tag="$2"

    # Like build.sh, map the base images used by the Dockerfile (FROM system_tests_base_*) to their locked tags
    local base_image_context_args=()
    local base_image_contexts
    base_image_contexts=$(python3 utils/scripts/resolve-base-images-contexts.py --build-contexts "$dockerfile")
    if [[ -n "$base_image_contexts" ]]; then
        while IFS= read -r base_image_context; do
            base_image_context_args+=(--build-context "$base_image_context")
        done <<< "$base_image_contexts"
    fi

    docker buildx build --load --progress=plain "${base_image_context_args[@]}" -f "$dockerfile" -t "$tag" .
}

build_buddy utils/build/docker/python/flask-poc.Dockerfile datadog/system-tests:python_buddy-v2
build_buddy utils/build/docker/nodejs/express4.Dockerfile datadog/system-tests:nodejs_buddy-v1
build_buddy utils/build/docker/java/spring-boot.Dockerfile datadog/system-tests:java_buddy-v1
build_buddy utils/build/docker/ruby/rails72.Dockerfile datadog/system-tests:ruby_buddy-v2
build_buddy utils/build/docker/golang/net-http.Dockerfile datadog/system-tests:golang_buddy-v2


if [ "${1:-}" = "--push" ]; then
      docker push datadog/system-tests:python_buddy-v2
      docker push datadog/system-tests:nodejs_buddy-v1
      docker push datadog/system-tests:java_buddy-v1
      docker push datadog/system-tests:ruby_buddy-v2
      docker push datadog/system-tests:golang_buddy-v2
fi
