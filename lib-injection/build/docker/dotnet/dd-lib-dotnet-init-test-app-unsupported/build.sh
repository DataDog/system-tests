#!/bin/bash

if [ -z "${BUILDX_PLATFORMS}" ] ; then
    BUILDX_PLATFORMS="linux/amd64"
fi

docker buildx build --platform ${BUILDX_PLATFORMS} --tag ${LIBRARY_INJECTION_TEST_APP_IMAGE} --push .