FROM python:3.13-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl

# print versions
RUN python --version && curl --version
# install python deps
ENV PIP_ROOT_USER_ACTION=ignore
RUN pip install --upgrade pip
RUN pip install django==5.2.6 pycryptodome==3.23.0 gunicorn==23.0.0 gevent==25.8.2 requests==2.32.4 boto3==1.34.141 \
    'moto[ec2,s3,all]'==5.0.14 xmltodict==0.14.2 zope.event==5.1.1 zope.interface==7.2 openfeature-sdk==0.8.3

# docker build --progress=plain -f utils/build/docker/python/django-py3.13.base.Dockerfile -t datadog/system-tests:django-py3.13.base-v6 .
# docker push datadog/system-tests:django-py3.13.base-v6
