FROM golang:1.25-alpine AS build

RUN apk add --no-cache jq curl bash gcc musl-dev git

# print important lib versions
RUN go version && curl --version

# build application binary
COPY utils/build/docker/golang/app/ /app/
# Note: this is a workaround to avoid the orchestrion build to fail, as using
# WORKDIR /app will fail with the following error:
# main module (systemtests.weblog) does not contain package systemtests.weblog/net-http-orchestrion
WORKDIR /app/net-http-orchestrion

ENV GOCACHE=/root/.cache/go-build \
    GOMODCACHE=/go/pkg/mod \
    GONOSUMDB=github.com/DataDog/* \
    GOPRIVATE=github.com/DataDog/*
# Use the optional github_token BuildKit secret for private Go modules without
# persisting the credential. Local builds continue to work without the secret.
RUN --mount=type=secret,id=github_token                                        \
    --mount=type=cache,target=${GOMODCACHE}                                     \
    --mount=type=cache,target=${GOCACHE}                                        \
    --mount=type=tmpfs,target=/tmp                                              \
    --mount=type=bind,source=utils/build/docker/golang,target=/utils            \
    --mount=type=bind,source=binaries,target=/binaries                          \
  if [ -f /run/secrets/github_token ]; then                                     \
    export GIT_CONFIG_COUNT=1                                                   \
           GIT_CONFIG_KEY_0="url.https://x-access-token:$(cat /run/secrets/github_token)@github.com/.insteadOf" \
           GIT_CONFIG_VALUE_0="https://github.com/";                            \
  fi &&                                                                         \
  go mod download && go mod verify &&                                           \
  /utils/install_ddtrace.sh &&                                                  \
  /utils/install_orchestrion.sh &&                                              \
  orchestrion go build -v -tags=appsec -o=/app/weblog .

# ==============================================================================

FROM golang:1.25-alpine

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
