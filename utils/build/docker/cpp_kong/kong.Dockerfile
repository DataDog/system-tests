# ubuntu:24.04 ships with cmake 3.28 (minimum version required by dd-trace-cpp)
FROM ubuntu:24.04 AS build

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates cmake g++ make libcurl4-openssl-dev git jq curl unzip && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir /builds /binaries

COPY binaries/ /binaries/
COPY utils/build/docker/cpp_kong/install_ddtrace.sh /binaries/install_ddtrace.sh
COPY utils/build/docker/github.sh /binaries/github.sh
RUN --mount=type=secret,id=github_token /binaries/install_ddtrace.sh

# ==============================================================================

FROM kong/kong-gateway:3.4

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /builds

# Install the dd-trace-cpp C binding library
COPY --from=build /usr/local/lib/libdd_trace_c.so /usr/local/lib/
RUN ldconfig

# Install the Kong plugin Lua files
COPY --from=build /binaries/kong-plugin-ddtrace/kong/plugins/ddtrace/ \
    /usr/local/share/lua/5.1/kong/plugins/ddtrace/

# Copy version metadata
COPY --from=build /builds/healthcheck.json /builds/healthcheck.json
COPY --from=build /builds/SYSTEM_TESTS_LIBRARY_VERSION /builds/SYSTEM_TESTS_LIBRARY_VERSION

# Static response files for weblog endpoints
RUN printf 'Hello world!\n' > /builds/hello.txt
RUN printf 'Hello headers!\n' > /builds/headers.txt

# Kong declarative config and internal backend server block
COPY utils/build/docker/cpp_kong/kong.yaml /kong/declarative/kong.yaml
COPY utils/build/docker/cpp_kong/backend.conf /kong/backend.conf

WORKDIR /builds
RUN printf '#!/bin/bash\nexec /entrypoint.sh kong docker-start\n' > app.sh
RUN chmod +x app.sh

ENV KONG_DATABASE=off
ENV KONG_DECLARATIVE_CONFIG=/kong/declarative/kong.yaml
ENV KONG_PLUGINS=bundled,ddtrace
ENV KONG_PROXY_ACCESS_LOG=/dev/stdout
ENV KONG_PROXY_ERROR_LOG=/dev/stderr
ENV KONG_ADMIN_LISTEN=0.0.0.0:8001
ENV KONG_LOG_LEVEL=info
ENV KONG_PROXY_LISTEN=0.0.0.0:7777
ENV KONG_NGINX_HTTP_INCLUDE=/kong/backend.conf

EXPOSE 7777

CMD ["./app.sh"]
