
FROM datadog/docker-library:dd-trace-cpp-ci AS build

RUN apt-get update && apt-get -y install pkg-config libabsl-dev curl jq
WORKDIR /usr/app
COPY utils/build/docker/cpp/parametric/install_ddtrace.sh binaries* /binaries/
RUN sh /binaries/install_ddtrace.sh
RUN cd /binaries/dd-trace-cpp  && cmake -B .build -DCMAKE_BUILD_TYPE=Release -DDD_TRACE_BUILD_TESTING=1 .  && cmake --build .build -j $(nproc)  && cmake --install .build --prefix /usr/app/

FROM ubuntu:22.04
COPY --from=build /usr/app/bin/parametric-http-server /usr/local/bin/parametric-http-server
