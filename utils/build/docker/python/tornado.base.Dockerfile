FROM python:3.14-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl

# print versions
RUN python --version && curl --version

# install python deps
COPY utils/build/docker/python/tornado/requirements-tornado.txt /tmp/tornado-requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/tornado-requirements.txt

RUN mkdir app
WORKDIR /app

# py-spy lets system-tests dump a weblog's thread stacks from outside the
# process when a remote config apply stalls (see utils/_remote_config.py)
RUN pip install --no-cache-dir py-spy==0.4.2

# docker build --progress=plain -f utils/build/docker/python/tornado.base.Dockerfile -t datadog/system-tests:tornado.base-v3 .
# docker push datadog/system-tests:tornado.base-v3
