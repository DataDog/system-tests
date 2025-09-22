FROM python:3.14-rc-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl

# print versions
RUN python --version && curl --version

# install python deps
RUN pip install --upgrade pip
RUN pip install PyYAML fastapi uvicorn requests cryptography==42.0.8 pycryptodome python-multipart jinja2 psycopg itsdangerous xmltodict==0.14.2

RUN mkdir app
WORKDIR /app

# docker build --progress=plain -f utils/build/docker/python/fastapi.base.Dockerfile -t datadog/system-tests:fastapi.base-v7 .
# docker push datadog/system-tests:fastapi.base-v7
