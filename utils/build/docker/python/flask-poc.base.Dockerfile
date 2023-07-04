FROM python:3.9-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl git gcc g++

# print versions
RUN python --version && curl --version

# install python deps
# Tracer does not support flask 2.3.0 or higher, pin the flask version for now
RUN pip install flask==2.2.4 gunicorn gevent requests pycryptodome psycopg2-binary

# docker build --progress=plain -f utils/build/docker/python/flask-poc.base.Dockerfile -t datadog/system-tests:flask-poc.base-v0 .
# docker push datadog/system-tests:flask-poc.base-v0

