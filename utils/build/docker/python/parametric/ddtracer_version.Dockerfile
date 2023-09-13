
FROM python:3.9-slim

ARG PYTHON_DDTRACE_PACKAGE=ddtrace
ENV PYTHON_DDTRACE_PACKAGE=$PYTHON_DDTRACE_PACKAGE

WORKDIR /client

# install bin dependancies
RUN apt-get update && apt-get install -y git gcc g++ make cmake

COPY ./utils/build/docker/python/parametric/ddtracer_version.sh .
RUN sh ddtracer_version.sh
CMD cat SYSTEM_TESTS_LIBRARY_VERSION
