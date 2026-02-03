#!/usr/bin/env bash
set -e

if [ "$1" = "--push" ]; then
    exec docker buildx bake --progress=plain -f "utils/build/docker/python/docker-bake.hcl" "$@"
else
    exec docker buildx bake --progress=plain --load -f "utils/build/docker/python/docker-bake.hcl" "$@"
fi
