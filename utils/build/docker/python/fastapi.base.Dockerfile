FROM python:3.11-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl

# print versions
RUN python --version && curl --version

# install python deps
COPY utils/build/docker/python/fastapi/requirements-fastapi.txt /tmp/fastapi-requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/fastapi-requirements.txt

RUN mkdir app
WORKDIR /app

# docker build --progress=plain -f utils/build/docker/python/fastapi.base.Dockerfile -t datadog/system-tests:fastapi.base-v8 .
# docker push datadog/system-tests:fastapi.base-v8
