#!/usr/bin/env bash
set -Eeuo pipefail

# build and push python base images

docker_build() {
    docker buildx build --progress=plain "$@"
}

docker_build -f utils/build/docker/python/django-py3.13.base.Dockerfile -t datadog/system-tests:django-py3.13.base-v4 "$@" .
docker_build -f utils/build/docker/python/fastapi.base.Dockerfile       -t datadog/system-tests:fastapi.base-v6       "$@" .
docker_build -f utils/build/docker/python/python3.12.base.Dockerfile    -t datadog/system-tests:python3.12.base-v9    "$@" .
docker_build -f utils/build/docker/python/django-poc.base.Dockerfile    -t datadog/system-tests:django-poc.base-v7    "$@" .
docker_build -f utils/build/docker/python/flask-poc.base.Dockerfile     -t datadog/system-tests:flask-poc.base-v11    "$@" .
docker_build -f utils/build/docker/python/uwsgi-poc.base.Dockerfile     -t datadog/system-tests:uwsgi-poc.base-v7     "$@" .

