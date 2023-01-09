#!/bin/bash

docker buildx build --platform "linux/amd64" --tag "spring_native_build" --push .