#!/usr/bin/env bash

export DOCKER_IMAGE_WEBLOG_TAG=latest

APP_DOCKER_IMAGE_REPO=ghcr.io/datadog/system-tests/dd-lib-dotnet-init-test-app LIBRARY_INJECTION_TEST_APP_IMAGE=ghcr.io/datadog/system-tests/dd-lib-dotnet-init-test-app:$DOCKER_IMAGE_WEBLOG_TAG ./lib-injection/build/docker/dotnet/dd-lib-dotnet-init-test-app/build.sh
