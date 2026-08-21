
FROM golang:1.25

# install jq
RUN apt-get update && apt-get -y install jq
ENV GONOSUMDB=github.com/DataDog/* \
    GOPRIVATE=github.com/DataDog/*
WORKDIR /app
COPY utils/build/docker/golang/parametric/go.mod /app
COPY utils/build/docker/golang/parametric/go.sum /app
COPY utils/build/docker/golang/parametric/. /app
# download the proper tracer version
COPY utils/build/docker/golang/install_ddtrace.sh binaries* /binaries/
COPY utils/build/docker/golang/parametric/system_tests_library_version.sh system_tests_library_version.sh
RUN /binaries/install_ddtrace.sh
RUN mkdir /parametric-tracer-logs

# Go ignores underscore-prefixed files, keeping tracer versions without llmobs/export buildable.
RUN if go list github.com/DataDog/dd-trace-go/v2/llmobs/export >/dev/null 2>&1; then \
        cp _llmobs_export_supported.go llmobs_export_supported.go; \
    fi \
    && go mod tidy \
    && go install

CMD ["main"]
