FROM python:3.11-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl git gcc g++ make cmake

# print versions
RUN python --version && curl --version

# install python deps
RUN pip install --upgrade pip
RUN pip install PyYAML fastapi uvicorn requests cryptography==42.0.8 pycryptodome python-multipart jinja2 psycopg2-binary itsdangerous xmltodict==0.14.2

# Install Rust toolchain
RUN curl https://sh.rustup.rs -sSf | sh -s -- --default-toolchain stable -y
ENV PATH="/root/.cargo/bin:$PATH"

RUN mkdir app
WORKDIR /app

# docker build --progress=plain -f utils/build/docker/python/fastapi.base.Dockerfile -t datadog/system-tests:fastapi.base-v0 .
# docker push datadog/system-tests:fastapi.base-v0
