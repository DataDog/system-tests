#!/bin/bash

if [ -z "${BUILDX_PLATFORMS}" ]; then
    BUILDX_PLATFORMS="linux/amd64"
fi
if [ -z "${RUNTIME}" ]; then
    RUNTIME="bullseye-slim"
fi
docker buildx build --build-arg RUNTIME=${RUNTIME} --platform ${BUILDX_PLATFORMS} --tag ${LIBRARY_INJECTION_TEST_APP_IMAGE} --push .
