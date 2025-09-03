FROM python:3.11-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl

# print versions
RUN python --version && curl --version

# install python deps
ENV PIP_ROOT_USER_ACTION=ignore
RUN pip install --upgrade pip
RUN pip install django==5.2.4 pycryptodome==3.23.0 gunicorn==21.2.0 gevent==25.5.1 requests==2.32.4 boto3==1.34.141 'moto[ec2,s3,all]'==5.0.14 xmltodict==0.14.2

# docker build --progress=plain -f utils/build/docker/python/django-poc.base.Dockerfile -t datadog/system-tests:django-poc.base-v7 .
# docker push datadog/system-tests:django-poc.base-v7

