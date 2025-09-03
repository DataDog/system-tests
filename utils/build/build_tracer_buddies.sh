#!/usr/bin/env bash

# buddies are weblog app in another lang
# they are used in the CROSSED_TRACING_LIBRARIES scenario, where we can tests data propagation between different languages

if [ "$1" = "--push" ]; then
    BUILD_ARGS="--push --progress=plain"
else
    BUILD_ARGS="--load --progress=plain"
fi

docker buildx build $BUILD_ARGS -f utils/build/docker/python/flask-poc.Dockerfile -t datadog/system-tests:python_buddy-v1 .
docker buildx build $BUILD_ARGS -f utils/build/docker/nodejs/express4.Dockerfile -t datadog/system-tests:nodejs_buddy-v1 .
docker buildx build $BUILD_ARGS -f utils/build/docker/java/spring-boot.Dockerfile -t datadog/system-tests:java_buddy-v1 .
docker buildx build $BUILD_ARGS -f utils/build/docker/ruby/rails70.Dockerfile -t datadog/system-tests:ruby_buddy-v1 .
docker buildx build $BUILD_ARGS -f utils/build/docker/golang/net-http.Dockerfile -t datadog/system-tests:golang_buddy-v1 .

