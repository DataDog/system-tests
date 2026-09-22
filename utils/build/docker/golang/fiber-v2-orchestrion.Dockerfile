FROM golang:1.26-alpine AS build

RUN apk add --no-cache jq curl bash gcc musl-dev git

RUN go version && curl --version

COPY utils/build/docker/golang/app/ /app/
WORKDIR /app/fiber-v2-orchestrion

ENV GOCACHE=/root/.cache/go-build \
    GOMODCACHE=/go/pkg/mod \
    GONOSUMDB=github.com/DataDog/* \
    GOPRIVATE=github.com/DataDog/*
RUN --mount=type=cache,target=${GOMODCACHE} \
    --mount=type=cache,target=${GOCACHE} \
    --mount=type=tmpfs,target=/tmp \
    --mount=type=bind,source=utils/build/docker/golang,target=/utils \
    --mount=type=bind,source=binaries,target=/binaries \
    go mod download && go mod verify && \
    /utils/install_ddtrace.sh && \
    /utils/install_orchestrion.sh && \
    orchestrion go test -v -count=1 -tags=appsec,orchestrion ./... && \
    orchestrion go build -v -tags=appsec,orchestrion -o=/app/weblog .

FROM golang:1.26-alpine

RUN apk add --no-cache curl bash gcc musl-dev

COPY --from=build /app/weblog /app/weblog
COPY --from=build /app/fiber-v2-orchestrion/SYSTEM_TESTS_LIBRARY_VERSION /app/SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /app/SYSTEM_TESTS_ORCHESTRION_VERSION /app/SYSTEM_TESTS_ORCHESTRION_VERSION

WORKDIR /app
RUN printf '#!/bin/bash\nexec ./weblog\n' > app.sh && chmod +x app.sh
EXPOSE 7777
CMD ["./app.sh"]

ENV DD_LOGGING_RATE="0" \
    DD_TRACE_HEADER_TAGS="user-agent" \
    DD_DATA_STREAMS_ENABLED="true" \
    DD_ENV="system-tests" \
    DD_SERVICE="weblog" \
    DD_VERSION="1.0" \
    DD_PROFILING_ENABLED="true"
