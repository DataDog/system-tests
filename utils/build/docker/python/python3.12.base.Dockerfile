FROM python:3.12.1-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl git gcc g++ make cmake

# print versions
RUN python --version && curl --version

# install python deps
ENV PIP_ROOT_USER_ACTION=ignore
RUN pip install --upgrade pip
RUN pip install django pycryptodome gunicorn gevent requests

# docker build --progress=plain -f utils/build/docker/python/python3.12.base.Dockerfile -t datadog/system-tests:python3.12.base-v2 .
# docker push datadog/system-tests:python3.12.base-v2

