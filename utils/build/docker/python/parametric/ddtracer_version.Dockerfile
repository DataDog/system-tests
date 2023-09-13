
FROM python:3.9-slim

ARG PYTHON_DDTRACE_PACKAGE=ddtrace
ENV PYTHON_DDTRACE_PACKAGE=$PYTHON_DDTRACE_PACKAGE

WORKDIR /client

# install bin dependancies
RUN apt-get update && apt-get install -y curl git gcc g++ make cmake

COPY ddtracer_version.sh .
#RUN pyenv global 3.9.18
RUN python3.9 -m pip install grpcio==1.46.3 grpcio-tools==1.46.3
RUN sh ddtracer_version.sh
#RUN python3.9 -m pip install ddtrace
CMD cat SYSTEM_TESTS_LIBRARY_VERSION
