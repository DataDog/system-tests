FROM datadog/docker-library:dd-trace-cpp-ci AS build

RUN apt-get update && apt-get -y install pkg-config libabsl-dev
WORKDIR /cpp-parametric-test
ADD CMakeLists.txt \
    developer_noise.cpp \
    developer_noise.h \
    httplib.h \
    json.hpp \
    main.cpp \
    manual_scheduler.h \
    request_handler.cpp \
    request_handler.h \
    utils.h \
    /cpp-parametric-test/
RUN cmake -B .build -DCMAKE_BUILD_TYPE=Release . && cmake --build .build -j $(nproc) && cmake --install .build --prefix dist

FROM ubuntu:22.04
COPY --from=build /cpp-parametric-test/dist/bin/cpp-parametric-http-test /usr/local/bin/cpp-parametric-test
