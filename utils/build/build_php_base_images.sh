#!/usr/bin/env bash
set -e

# When pushing, build a multi-arch manifest (amd64 + arm64). Local runs use
# --load, which only supports a single platform, so we leave PLATFORMS empty
# and let buildx build for the host arch only.
if [ "$1" = "--push" ]; then
    exec env PLATFORMS="linux/amd64,linux/arm64" \
        docker buildx bake --progress=plain -f "utils/build/docker/php/docker-bake.hcl" "$@"
else
    exec docker buildx bake --progress=plain --load -f "utils/build/docker/php/docker-bake.hcl" "$@"
fi
