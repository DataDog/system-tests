#!/usr/bin/env bash
set -Eeuo pipefail

docker buildx build \
    --progress=plain \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    -f utils/build/docker/lambda-proxy.Dockerfile \
    -t datadog/system-tests:lambda-proxy-v1 \
    "$@" \
    .
