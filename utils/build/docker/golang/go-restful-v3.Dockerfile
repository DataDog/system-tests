FROM golang:1.26-alpine AS build

RUN apk add --no-cache jq curl bash gcc musl-dev git

RUN go version && curl --version

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
  go build -v -tags=appsec -o=./weblog ./go-restful-v3

FROM golang:1.26-alpine

RUN apk add --no-cache curl bash gcc musl-dev

COPY --from=build /app/weblog /app/weblog
COPY --from=build /app/SYSTEM_TESTS_LIBRARY_VERSION /app/SYSTEM_TESTS_LIBRARY_VERSION

WORKDIR /app

ENV DD_TRACE_HEADER_TAGS='user-agent' \
    DD_DATA_STREAMS_ENABLED=true \
    DD_LOGGING_RATE=0

COPY utils/build/docker/golang/app.sh app.sh
RUN chmod +x app.sh
CMD ["./app.sh"]
