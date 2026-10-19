FROM python:3.11.16-slim@sha256:e41613d42d4891e4930f79523f93f81bbc7632584ec65e36ab055f41a800b41e

# install bin dependancies
RUN apt-get update && apt-get install -y gcc curl

# print versions
RUN python --version && curl --version

# this is necessary for the mysqlclient install
RUN apt update && apt install -y pkg-config default-libmysqlclient-dev pkg-config

# install python deps
# Tracer does not support flask 2.3.0 or higher, pin the flask version in the requirements file.
COPY flask/requirements-uwsgi-poc.txt /tmp/flask-requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/flask-requirements.txt
