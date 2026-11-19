# The base image is ubuntu:24.04 with the build toolchain installed (see kong-build.base.Dockerfile)
FROM system_tests_base_cpp_kong_kong_build AS build

RUN mkdir /builds /binaries

COPY binaries/ /binaries/
COPY utils/build/docker/cpp_kong/install_ddtrace.sh /binaries/install_ddtrace.sh
COPY utils/build/docker/github.sh /binaries/github.sh
RUN --mount=type=secret,id=github_token /binaries/install_ddtrace.sh

# ==============================================================================

# The base image is kong/kong-gateway:3.4 with curl installed, running as root (see kong-runtime.base.Dockerfile)
FROM system_tests_base_cpp_kong_kong_runtime

RUN mkdir -p /builds

# Install the dd-trace-cpp C binding library
COPY --from=build /usr/local/lib/libdd_trace_c.so /usr/local/lib/
RUN ldconfig

# Install the Kong plugin Lua files
COPY --from=build /binaries/kong-plugin-ddtrace/kong/plugins/ddtrace/ \
    /usr/local/share/lua/5.1/kong/plugins/ddtrace/

# Copy version metadata
COPY --from=build /builds/healthcheck.json /builds/healthcheck.json
COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION /binaries/SYSTEM_TESTS_LIBRARY_VERSION

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
