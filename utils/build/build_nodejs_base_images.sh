#!/usr/bin/env bash

set -e

# build and push nodejs base images

docker buildx build --load --progress=plain -f utils/build/docker/nodejs/express4.base.Dockerfile -t datadog/system-tests:express4.base-v0 .
docker buildx build --load --progress=plain -f utils/build/docker/nodejs/nextjs.base.Dockerfile -t datadog/system-tests:nextjs.base-v0 .

if [ "$1" = "--push" ]; then
      docker push datadog/system-tests:express4.base-v0
      docker push datadog/system-tests:nextjs.base-v0
fi
