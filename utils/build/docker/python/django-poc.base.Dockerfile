FROM python:3.11-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl git gcc g++ make cmake

# print versions
RUN python --version && curl --version

# install python deps
ENV PIP_ROOT_USER_ACTION=ignore
RUN pip install --upgrade pip
RUN pip install django pycryptodome gunicorn==21.2.0 gevent requests 'moto[ec2,s3,all]'==5.0.14 boto3==1.34.141 xmltodict==0.14.2

# Install Rust toolchain
RUN curl https://sh.rustup.rs -sSf | sh -s -- --default-toolchain stable -y
ENV PATH="/root/.cargo/bin:$PATH"

# docker build --progress=plain -f utils/build/docker/python/django-poc.base.Dockerfile -t datadog/system-tests:django-poc.base-v0 .
# docker push datadog/system-tests:django-poc.base-v0

