FROM golang:1.24-alpine3.22 AS build

RUN apk add --no-cache jq curl bash gcc musl-dev

# print important lib versions
RUN go version && curl --version

# build application binary
COPY utils/build/docker/golang/app/ /app/
# Note: this is a workaround to avoid the orchestrion build to fail, as using
# WORKDIR /app will fail with the following error:
# main module (systemtests.weblog) does not contain package systemtests.weblog/net-http-orchestrion
WORKDIR /app/net-http-orchestrion

ENV GOCACHE=/root/.cache/go-build \
    GOMODCACHE=/go/pkg/mod
RUN --mount=type=cache,target=${GOMODCACHE}                                     \
    --mount=type=cache,target=${GOCACHE}                                        \
    --mount=type=tmpfs,target=/tmp                                              \
    --mount=type=bind,source=utils/build/docker/golang,target=/utils            \
    --mount=type=bind,source=binaries,target=/binaries                          \
  go mod download && go mod verify &&                                           \
  /utils/install_ddtrace.sh &&                                                  \
  /utils/install_orchestrion.sh &&                                              \
  orchestrion go build -v -tags=appsec -o=/app/weblog .

# ==============================================================================

FROM golang:1.24-alpine3.22

RUN apk add --no-cache curl bash gcc musl-dev

COPY --from=build /app/weblog /app/weblog
COPY --from=build /app/net-http-orchestrion/SYSTEM_TESTS_LIBRARY_VERSION /app/SYSTEM_TESTS_LIBRARY_VERSION

WORKDIR /app

RUN printf "#!/bin/bash\nexec ./weblog" > app.sh
RUN chmod +x app.sh
CMD ["./app.sh"]

# Datadog setup
ENV DD_LOGGING_RATE="0" \
  DD_TRACE_HEADER_TAGS="user-agent" \
  DD_DATA_STREAMS_ENABLED="true" \
  # Set up the environment so the profiler starts appropriately...
  DD_ENV="system-tests" \
  DD_SERVICE="weblog" \
  DD_VERSION="1.0" \
  DD_PROFILING_ENABLED="true"
