
FROM system_tests_base_cpp_cpp_parametric AS build

WORKDIR /usr/app
COPY utils/build/docker/cpp/parametric/install_ddtrace.sh binaries* /binaries/
COPY utils/build/docker/github.sh /binaries/github.sh
RUN --mount=type=secret,id=github_token /binaries/install_ddtrace.sh
RUN cd /binaries/dd-trace-cpp \
 && cmake -B .build -DCMAKE_BUILD_TYPE=Release -DDD_TRACE_BUILD_TESTING=1 . \
 && cmake --build .build -j $(nproc) \
 && cmake --install .build --prefix /usr/app/

FROM ubuntu:22.04
COPY --from=build /usr/app/bin/parametric-http-server /usr/local/bin/parametric-http-server
COPY --from=build /usr/app/SYSTEM_TESTS_LIBRARY_VERSION /SYSTEM_TESTS_LIBRARY_VERSION
RUN mkdir /parametric-tracer-logs

CMD ["parametric-http-server"]
