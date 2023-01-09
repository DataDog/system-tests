#!/bin/bash

docker buildx build --platform "linux/amd64" --tag "datadog/system_tests/spring_native_build:latest" --push .