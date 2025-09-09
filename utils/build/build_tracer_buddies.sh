#!/usr/bin/env bash
set -Eeuo pipefail

# buddies are weblog app in another lang
# they are used in the CROSSED_TRACING_LIBRARIES scenario, where we can tests data propagation between different languages

docker_build() {
    docker buildx build --progress=plain "$@"
}

docker_build -f utils/build/docker/python/flask-poc.Dockerfile -t datadog/system-tests:python_buddy-v2 "$@" .
docker_build -f utils/build/docker/nodejs/express4.Dockerfile  -t datadog/system-tests:nodejs_buddy-v1 "$@" .
docker_build -f utils/build/docker/java/spring-boot.Dockerfile -t datadog/system-tests:java_buddy-v1   "$@" .
docker_build -f utils/build/docker/ruby/rails72.Dockerfile     -t datadog/system-tests:ruby_buddy-v2   "$@" .
docker_build -f utils/build/docker/golang/net-http.Dockerfile  -t datadog/system-tests:golang_buddy-v1 "$@" .

