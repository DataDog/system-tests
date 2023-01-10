#!/bin/bash

docker buildx build --platform "linux/amd64" --tag "ghcr.io/datadog/system-tests/java11_mvn_build:latest" --push .