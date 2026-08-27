FROM golang:1.25-alpine AS build

RUN apk add --no-cache jq curl bash gcc musl-dev git

# print important lib versions
RUN go version && curl --version

# build application binary
COPY utils/build/docker/golang/app/ /app/
WORKDIR /app

ENV GOCACHE=/root/.cache/go-build \
    GOMODCACHE=/go/pkg/mod \
    GONOSUMDB=github.com/DataDog/* \
    GOPRIVATE=github.com/DataDog/*
RUN --mount=type=cache,target=${GOMODCACHE}                                     \
    --mount=type=cache,target=${GOCACHE}                                        \
    --mount=type=tmpfs,target=/tmp                                              \
    --mount=type=bind,source=utils/build/docker/golang,target=/utils            \
    --mount=type=bind,source=binaries,target=/binaries                          \
  go mod download && go mod verify &&                                           \
  /utils/install_ddtrace.sh &&                                                  \
  go build -v -tags=appsec -o=./weblog ./net-http

# ==============================================================================

FROM golang:1.25-alpine

RUN apk add --no-cache curl bash gcc musl-dev ca-certificates

# Agentless intake tests send HTTPS through the system-tests mitmproxy. Trust the
# checked-in test CA so Go validates that intercepted TLS connection.
COPY ./utils/proxy/.mitmproxy/mitmproxy-ca-cert.cer /usr/local/share/ca-certificates/system-tests-mitmproxy-ca.crt
RUN update-ca-certificates

COPY --from=build /app/weblog /app/weblog
COPY --from=build /app/SYSTEM_TESTS_LIBRARY_VERSION /app/SYSTEM_TESTS_LIBRARY_VERSION

WORKDIR /app

# Datadog setup
ENV DD_TRACE_HEADER_TAGS='user-agent' \
    DD_DATA_STREAMS_ENABLED=true \
    DD_LOGGING_RATE=0

RUN printf "#!/bin/bash\nexec ./weblog" > app.sh
RUN chmod +x app.sh
CMD ["./app.sh"]
