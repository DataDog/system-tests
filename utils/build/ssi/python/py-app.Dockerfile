ARG BASE_IMAGE

FROM ubuntu:jammy as python

RUN DEBIAN_FRONTEND=noninteractive \
  apt update && \
  apt install software-properties-common && \
  add-apt-repository ppa:deadsnakes/ppa && apt update && apt install python3.12

FROM ${BASE_IMAGE}
WORKDIR /app
COPY --from=python /usr/lib/python3.12 /usr/lib/python3.12
COPY lib-injection/build/docker/python/dd-lib-python-init-test-django/ .
ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE django_app
RUN pip install django
EXPOSE 18080
CMD python -m django runserver 0.0.0.0:18080
