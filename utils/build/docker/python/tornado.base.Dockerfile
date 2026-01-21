FROM python:3.14-rc-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl

# print versions
RUN python --version && curl --version

# install python deps
COPY utils/build/docker/python/tornado/requirements-tornado.txt /tmp/tornado-requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/tornado-requirements.txt

RUN mkdir app
WORKDIR /app

# docker build --progress=plain -f utils/build/docker/python/tornado.base.Dockerfile -t datadog/system-tests:tornado.base-v1 .
# docker push datadog/system-tests:tornado.base-v1
