FROM python:3.12.1-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl git gcc g++ make cmake

# print versions
RUN python --version && curl --version

# install python deps
RUN pip install django pycryptodome gunicorn gevent requests

RUN mkdir app
RUN django-admin startproject django_app app
WORKDIR /app
RUN python3 manage.py startapp app

RUN sed -i "1s/^/from django.urls import include\n/" django_app/urls.py
RUN sed -i "s/admin\///g" django_app/urls.py
RUN sed -i "s/admin.site.urls/include(\"app.urls\")/g" django_app/urls.py
RUN sed -i "s/ALLOWED_HOSTS\s=\s\[\]/ALLOWED_HOSTS = \[\"0.0.0.0\",\"weblog\"\,\"localhost\"\]/g" django_app/settings.py


# docker build --progress=plain -f utils/build/docker/python/python3.12.base.Dockerfile -t datadog/system-tests:python3.12.base-v0 .
# docker push datadog/system-tests:python3.12.base-v0

