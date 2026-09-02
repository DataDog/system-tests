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

# py-spy lets system-tests dump a weblog's thread stacks from outside the
# process when a remote config apply stalls (see utils/_remote_config.py)
RUN pip install --no-cache-dir py-spy==0.4.2

# docker build --progress=plain -f utils/build/docker/python/fastapi.base.Dockerfile -t datadog/system-tests:fastapi.base-v10 .
# docker push datadog/system-tests:fastapi.base-v10
