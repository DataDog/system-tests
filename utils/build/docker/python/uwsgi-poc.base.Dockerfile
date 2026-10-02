FROM python:3.11-slim

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
