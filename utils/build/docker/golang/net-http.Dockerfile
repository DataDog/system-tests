FROM golang:golang:1.24-alpine3.22 AS build 

RUN apk add --no-cache jq curl bash gcc musl-dev

# print important lib versions
RUN go version && curl --version

# build application binary
COPY utils/build/docker/golang/app/ /app/
WORKDIR /app

ENV GOCACHE=/root/.cache/go-build \
    GOMODCACHE=/go/pkg/mod \
    CGO_ENABLED=1
RUN --mount=type=cache,target=${GOMODCACHE}                                     \
    --mount=type=cache,target=${GOCACHE}                                        \
    --mount=type=tmpfs,target=/tmp                                              \
    --mount=type=bind,source=utils/build/docker/golang,target=/utils            \
    --mount=type=bind,source=binaries,target=/binaries                          \
  go mod download && go mod verify &&                                           \
  /utils/install_ddtrace.sh &&                                                  \
  go build -v -tags=appsec -o=./weblog ./net-http

# ==============================================================================

FROM golang:golang:1.24-alpine3.22

RUN apk add --no-cache curl bash gcc musl-dev

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
