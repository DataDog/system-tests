FROM python:3.14-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl

# print versions
RUN python --version && curl --version

# install python deps
COPY tornado/requirements-tornado.txt /tmp/tornado-requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/tornado-requirements.txt

RUN mkdir app
WORKDIR /app
