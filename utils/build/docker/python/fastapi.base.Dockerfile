FROM python:3.12.0rc3-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl git gcc g++ make cmake

# print versions
RUN python --version && curl --version

# install python deps
RUN pip install fastapi

RUN mkdir app
WORKDIR /app
RUN app.sh


# docker build --progress=plain -f utils/build/docker/python/python3.12.base.Dockerfile -t datadog/system-tests:python3.12.base-v0 .
# docker push datadog/system-tests:python3.12.base-v0

