
FROM node:18.10-slim

ARG BUILD_MODULE=''
ENV NODEJS_DDTRACE_MODULE=$BUILD_MODULE
RUN apt-get update && apt-get install -y jq

WORKDIR /client
COPY ./utils/build/docker/nodejs/parametric/package.json /client/
COPY ./utils/build/docker/nodejs/parametric/package-lock.json /client/
COPY ./utils/build/docker/nodejs/parametric/*.js /client/
COPY ./utils/build/docker/nodejs/parametric/npm/* /client/
COPY ./utils/build/docker/nodejs/parametric/ddtracer_version.sh .
RUN sh ddtracer_version.sh
CMD cat SYSTEM_TESTS_LIBRARY_VERSION