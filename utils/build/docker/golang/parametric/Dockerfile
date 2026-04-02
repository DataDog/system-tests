
FROM golang:1.25

# install jq
RUN apt-get update && apt-get -y install jq
WORKDIR /app
COPY utils/build/docker/golang/parametric/go.mod /app
COPY utils/build/docker/golang/parametric/go.sum /app
COPY utils/build/docker/golang/parametric/. /app
# download the proper tracer version
COPY utils/build/docker/golang/install_ddtrace.sh binaries* /binaries/
COPY utils/build/docker/golang/parametric/system_tests_library_version.sh system_tests_library_version.sh
RUN /binaries/install_ddtrace.sh
RUN mkdir /parametric-tracer-logs

RUN go install

# Disable client-side p0 trace dropping so the test agent receives all traces
# regardless of sampling priority. Without this, Go drops p0 traces before
# transport (DD_TRACE_STATS_COMPUTATION_ENABLED defaults to true in dd-trace-go,
# and the test agent advertises client_drop_p0s:true), causing parametric tests
# with very low sampling rates to receive 0 traces.
ENV DD_TRACE_STATS_COMPUTATION_ENABLED=false

CMD ["main"]
