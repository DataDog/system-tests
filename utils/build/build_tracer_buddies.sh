#!/usr/bin/env bash

# buddies are weblog app in another lang
# they are used in the CROSSED_TRACING_LIBRARIES scenario, where we can tests data propagation between different languages 

docker buildx build --load --progress=plain -f utils/build/docker/python/flask-poc.Dockerfile -t datadog/system-tests:python_buddy-v0 .
docker buildx build --load --progress=plain -f utils/build/docker/nodejs/express4.Dockerfile -t datadog/system-tests:nodejs_buddy-v0 .

# Leave this line commented, it's only used when we need to push a new version of the buddy
# docker push datadog/system-tests:python_buddy-v0
docker push datadog/system-tests:nodejs_buddy-v0
