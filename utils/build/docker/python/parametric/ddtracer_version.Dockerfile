
FROM python:3.9-slim

ARG BUILD_MODULE=''
ENV PYTHON_DDTRACE_PACKAGE=$BUILD_MODULE

WORKDIR /client

# install bin dependancies
RUN apt-get update && apt-get install -y git gcc g++ make cmake

COPY ./utils/build/docker/python/parametric/ddtracer_version.sh .
RUN sh ddtracer_version.sh
CMD cat SYSTEM_TESTS_LIBRARY_VERSION
