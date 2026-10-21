FROM python:3.14-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl

# print versions
RUN python --version && curl --version

# install python deps
COPY aiohttp/requirements-aiohttp.txt /tmp/aiohttp-requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/aiohttp-requirements.txt

RUN mkdir app
WORKDIR /app
