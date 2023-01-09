#!/bin/bash

docker buildx build --platform "linux/amd64" --tag "ghcr.io/datadog/system-tests/spring_native_build:latest" --push .