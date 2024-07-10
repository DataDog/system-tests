#!/bin/bash

if [ -z "${BUILDX_PLATFORMS}" ] ; then
    BUILDX_PLATFORMS=`docker buildx imagetools inspect --raw python:3.12 | jq -r 'reduce (.manifests[] | [ .platform.os, .platform.architecture, .platform.variant ] | join("/") | sub("\\/$"; "")) as $item (""; . + "," + $item)' | sed 's/,//'`
fi
docker buildx build --platform ${BUILDX_PLATFORMS} --tag ${LIBRARY_INJECTION_TEST_APP_IMAGE} --push .