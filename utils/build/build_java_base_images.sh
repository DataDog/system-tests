#!/usr/bin/env bash

# build and push java base images

docker buildx build --load --progress=plain -f utils/build/docker/java/spring-boot.base.Dockerfile -t datadog/system-tests:spring-boot.base-v0 .

if [ "$1" = "--push" ]; then
      docker push datadog/system-tests:spring-boot.base-v0
fi
