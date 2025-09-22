FROM python:3.14-rc-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl

# print versions
RUN python --version && curl --version

# install python deps
RUN pip install --upgrade pip
RUN pip install PyYAML
RUN pip install pydantic==2.12.0a1
RUN pip install fastapi
RUN pip install uvicorn
RUN pip install requests
RUN pip install cryptography==42.0.8
RUN pip install pycryptodome
RUN pip install python-multipart
RUN pip install jinja2
RUN pip install psycopg
RUN pip install itsdangerous
RUN pip install xmltodict==0.14.2

RUN mkdir app
WORKDIR /app

# docker build --progress=plain -f utils/build/docker/python/fastapi.base.Dockerfile -t datadog/system-tests:fastapi.base-v7 .
# docker push datadog/system-tests:fastapi.base-v7
