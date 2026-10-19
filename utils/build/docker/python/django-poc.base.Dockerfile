FROM python:3.11.16-slim@sha256:e41613d42d4891e4930f79523f93f81bbc7632584ec65e36ab055f41a800b41e

# install bin dependancies
RUN apt-get update && apt-get install -y curl

# print versions
RUN python --version && curl --version

# install python deps
ENV PIP_ROOT_USER_ACTION=ignore
COPY django/requirements-django-poc.txt /tmp/django-requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/django-requirements.txt
