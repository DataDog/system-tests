FROM python:3.9-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl git gcc g++ make cmake

# print versions
RUN python --version && curl --version

# install python deps
# Tracer does not support flask 2.3.0 or higher, pin the flask version for now
RUN pip install flask==2.2.4 uwsgi gevent requests pycryptodome psycopg2-binary flask-login

# docker build --progress=plain -f utils/build/docker/python/uwsgi-poc.base.Dockerfile -t datadog/system-tests:uwsgi-poc.base-v0 .
# docker push datadog/system-tests:uwsgi-poc.base-v0

