FROM python:3.12-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl git gcc g++ make cmake

# print versions
RUN python --version && curl --version

# install python deps
ENV PIP_ROOT_USER_ACTION=ignore
RUN pip install --upgrade pip
RUN pip install django pycryptodome gunicorn gevent requests

# docker build --progress=plain -f utils/build/docker/python/django-poc.base.Dockerfile -t datadog/system-tests:django-poc.base-v0 .
# docker push datadog/system-tests:django-poc.base-v0

