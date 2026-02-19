
ARG GO_VERSION=1.25
FROM golang:${GO_VERSION}
ARG GO_VERSION

# install jq
RUN apt-get update && apt-get -y install jq
WORKDIR /app
COPY utils/build/docker/golang/parametric/go.mod /app
COPY utils/build/docker/golang/parametric/go.sum /app
RUN go mod edit -go=${GO_VERSION}
COPY utils/build/docker/golang/parametric/. /app
# download the proper tracer version
COPY utils/build/docker/golang/install_ddtrace.sh binaries* /binaries/
COPY utils/build/docker/golang/parametric/system_tests_library_version.sh system_tests_library_version.sh
RUN /binaries/install_ddtrace.sh
RUN mkdir /parametric-tracer-logs

RUN go install

CMD ["main"]
