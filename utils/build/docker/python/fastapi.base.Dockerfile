FROM python:3.11-slim


# print versions
RUN python --version

# install python deps
RUN pip install --upgrade pip
RUN pip install PyYAML fastapi uvicorn requests cryptography==42.0.8 pycryptodome python-multipart jinja2 psycopg2-binary itsdangerous xmltodict==0.14.2

RUN mkdir app
WORKDIR /app

# docker build --progress=plain -f utils/build/docker/python/fastapi.base.Dockerfile -t datadog/system-tests:fastapi.base-v6 .
# docker push datadog/system-tests:fastapi.base-v6
