#!/usr/bin/env bash

# buddies are weblog app in another lang
# they are used in the CROSSED_TRACING_LIBRARIES scenario, where we can tests data propagation between different languages

docker buildx build --load --progress=plain -f utils/build/docker/python/flask-poc.Dockerfile -t datadog/system-tests:python_buddy-v0 .
docker buildx build --load --progress=plain -f utils/build/docker/nodejs/express4.Dockerfile -t datadog/system-tests:nodejs_buddy-v0 .
docker buildx build --load --progress=plain -f utils/build/docker/java/spring-boot.Dockerfile -t datadog/system-tests:java_buddy-v0 .
docker buildx build --load --progress=plain -f utils/build/docker/ruby/rails70.Dockerfile -t datadog/system-tests:ruby_buddy-v0 .
docker buildx build --load --progress=plain -f utils/build/docker/golang/net-http.Dockerfile -t datadog/system-tests:golang_buddy-v0 .

# Otel buddies

docker buildx build --load --progress=plain -f utils/build/docker/python_otel/flask-poc-otel.Dockerfile -t datadog/system-tests:python_otel_buddy-v0 .


if [ "$1" = "--push" ]; then
      docker push datadog/system-tests:python_buddy-v0
      docker push datadog/system-tests:nodejs_buddy-v0
      docker push datadog/system-tests:java_buddy-v0
      docker push datadog/system-tests:ruby_buddy-v0
      docker push datadog/system-tests:golang_buddy-v0
      docker push datadog/system-tests:python_otel_buddy-v0
fi

