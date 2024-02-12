FROM python:3.10-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl git gcc g++ make cmake

# print versions
RUN python --version && curl --version

# install python deps
RUN pip install fastapi uvicorn

RUN mkdir app
WORKDIR /app

# docker build --progress=plain -f utils/build/docker/python/fastapi.base.Dockerfile -t datadog/system-tests:fastapi.base-v0 .
# docker push datadog/system-tests:fastapi.base-v0
