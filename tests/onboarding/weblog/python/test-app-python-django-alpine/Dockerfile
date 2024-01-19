FROM alpine:latest

# Install python/pip
ENV PYTHONUNBUFFERED=1
RUN apk add --update --no-cache python3 && ln -sf python3 /usr/bin/python
RUN apk add --no-cache bash

RUN rm /usr/lib/python3.11/EXTERNALLY-MANAGED

RUN python3 -m ensurepip
RUN pip3 install --no-cache --upgrade pip setuptools

ENV DJANGO_SETTINGS_MODULE django_app
WORKDIR /src
ADD . /src
RUN pip3 install django
EXPOSE 18080
CMD python3 -m django runserver 0.0.0.0:18080
