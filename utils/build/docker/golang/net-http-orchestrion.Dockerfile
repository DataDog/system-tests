FROM golang:1.24 AS build

# print important lib versions
RUN go version && curl --version

# download go dependencies
RUN mkdir -p /app
COPY utils/build/docker/golang/app/go.mod utils/build/docker/golang/app/go.sum /app/
WORKDIR /app
RUN go mod download && go mod verify

# copy the app code
COPY utils/build/docker/golang/app /app

# download the proper tracer version
COPY utils/build/docker/golang/install_*.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh && /binaries/install_orchestrion.sh

RUN orchestrion go build -v -tags appsec,orchestrion -o weblog ./net-http-orchestrion

# ==============================================================================

FROM golang:1.24

COPY --from=build /app/weblog /app/weblog
COPY --from=build /app/SYSTEM_TESTS_LIBRARY_VERSION /app/SYSTEM_TESTS_LIBRARY_VERSION

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
