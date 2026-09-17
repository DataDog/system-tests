FROM python:3.11-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl

# print versions
RUN python --version && curl --version

# install python deps
COPY fastapi/requirements-fastapi.txt /tmp/fastapi-requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/fastapi-requirements.txt

RUN mkdir app
WORKDIR /app
