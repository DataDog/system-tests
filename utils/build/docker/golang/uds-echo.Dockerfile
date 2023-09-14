FROM golang:1.20

# print important lib versions
RUN go version && curl --version

# install jq and socat
RUN apt-get update && apt-get -y install jq socat

# download go dependencies
RUN mkdir -p /app
COPY utils/build/docker/golang/app/go.mod utils/build/docker/golang/app/go.sum /app
WORKDIR /app
RUN go mod download && go mod verify

# copy the app code
COPY utils/build/docker/golang/app /app
COPY utils/build/docker/golang/app.sh /app/app.sh
COPY utils/build/docker/set-uds-transport.sh set-uds-transport.sh

# download the proper tracer version
COPY utils/build/docker/golang/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
ENV DD_TRACE_HEADER_TAGS='user-agent'

RUN go build -v -tags appsec -o weblog ./echo.go ./common.go ./grpc.go ./weblog_grpc.pb.go ./weblog.pb.go

ENV DD_APM_RECEIVER_SOCKET=/var/run/datadog/apm.socket
ENV UDS_WEBLOG=1

CMD ["./app.sh"]

# Datadog setup
ENV DD_LOGGING_RATE=0
