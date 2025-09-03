#!/usr/bin/env bash

if [ "$1" = "--push" ]; then
    BUILD_ARGS="--push --progress=plain"
else
    BUILD_ARGS="--load --progress=plain"
fi

docker buildx build $BUILD_ARGS -f utils/build/docker/python/django-py3.13.base.Dockerfile -t datadog/system-tests:django-py3.13.base-v4 .
docker buildx build $BUILD_ARGS -f utils/build/docker/python/fastapi.base.Dockerfile -t datadog/system-tests:fastapi.base-v6 .
docker buildx build $BUILD_ARGS -f utils/build/docker/python/python3.12.base.Dockerfile -t datadog/system-tests:python3.12.base-v9 .
docker buildx build $BUILD_ARGS -f utils/build/docker/python/django-poc.base.Dockerfile -t datadog/system-tests:django-poc.base-v7 .
docker buildx build $BUILD_ARGS -f utils/build/docker/python/flask-poc.base.Dockerfile -t datadog/system-tests:flask-poc.base-v11 .
docker buildx build $BUILD_ARGS -f utils/build/docker/python/uwsgi-poc.base.Dockerfile -t datadog/system-tests:uwsgi-poc.base-v7 .

