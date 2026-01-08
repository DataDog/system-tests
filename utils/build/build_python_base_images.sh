#!/usr/bin/env bash
exec docker buildx bake --progress=plain --load  -f "utils/build/docker/python/docker-bake.hcl" "$@"