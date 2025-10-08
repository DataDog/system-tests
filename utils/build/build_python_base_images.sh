#!/usr/bin/env bash

# build and push python base images



docker buildx build --load --progress=plain -f utils/build/docker/python/django-py3.13.base.Dockerfile -t datadog/system-tests:django-py3.13.base-v5 .
docker buildx build --load --progress=plain -f utils/build/docker/python/fastapi.base.Dockerfile -t datadog/system-tests:fastapi.base-v7 .
docker buildx build --load --progress=plain -f utils/build/docker/python/python3.12.base.Dockerfile -t datadog/system-tests:python3.12.base-v9 .
docker buildx build --load --progress=plain -f utils/build/docker/python/django-poc.base.Dockerfile -t datadog/system-tests:django-poc.base-v7 .
docker buildx build --load --progress=plain -f utils/build/docker/python/flask-poc.base.Dockerfile -t datadog/system-tests:flask-poc.base-v11 .
docker buildx build --load --progress=plain -f utils/build/docker/python/uwsgi-poc.base.Dockerfile -t datadog/system-tests:uwsgi-poc.base-v7 .

if [ "$1" = "--push" ]; then
      docker push datadog/system-tests:django-py3.13.base-v5
      docker push datadog/system-tests:fastapi.base-v7
      docker push datadog/system-tests:python3.12.base-v9
      docker push datadog/system-tests:django-poc.base-v7
      docker push datadog/system-tests:flask-poc.base-v11
      docker push datadog/system-tests:uwsgi-poc.base-v7
fi
