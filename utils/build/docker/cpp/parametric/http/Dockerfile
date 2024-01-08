
FROM datadog/docker-library:dd-trace-cpp-ci AS build

RUN apt-get update && apt-get -y install pkg-config libabsl-dev curl jq
WORKDIR /usr/app
COPY utils/build/docker/cpp/parametric/http/../install_ddtrace.sh binaries* /binaries/
ADD utils/build/docker/cpp/parametric/http/CMakeLists.txt     utils/build/docker/cpp/parametric/http/developer_noise.cpp     utils/build/docker/cpp/parametric/http/developer_noise.h     utils/build/docker/cpp/parametric/http/httplib.h     utils/build/docker/cpp/parametric/http/json.hpp     utils/build/docker/cpp/parametric/http/main.cpp     utils/build/docker/cpp/parametric/http/manual_scheduler.h     utils/build/docker/cpp/parametric/http/request_handler.cpp     utils/build/docker/cpp/parametric/http/request_handler.h     utils/build/docker/cpp/parametric/http/utils.h     /usr/app
RUN sh /binaries/install_ddtrace.sh
RUN cmake -B .build -DCMAKE_BUILD_TYPE=Release . && cmake --build .build -j $(nproc) && cmake --install .build --prefix dist

FROM ubuntu:22.04
COPY --from=build /usr/app/dist/bin/cpp-parametric-http-test /usr/local/bin/cpp-parametric-test
