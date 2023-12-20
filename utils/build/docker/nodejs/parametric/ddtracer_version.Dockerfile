
FROM node:18.10-slim

RUN apt-get update && apt-get install -y jq git

WORKDIR /usr/app

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

CMD cat SYSTEM_TESTS_LIBRARY_VERSION