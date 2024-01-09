FROM alpine:3.14

RUN apk add --no-cache curl git bash jq


WORKDIR /usr/app
COPY utils/build/docker/cpp/parametric/CMakeLists.txt .
COPY utils/build/docker/cpp/parametric/install_ddtrace.sh binaries* /binaries/

RUN sh /binaries/install_ddtrace.sh

CMD cat SYSTEM_TESTS_LIBRARY_VERSION
