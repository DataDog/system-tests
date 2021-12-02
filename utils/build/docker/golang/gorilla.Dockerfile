FROM golang:1

# print versions
RUN go version && curl --version

COPY utils/build/docker/golang/install_ddtrace.sh binaries* /binaries/
COPY utils/build/docker/golang/app /app

WORKDIR /app

RUN /binaries/install_ddtrace.sh

RUN go build -v -tags appsec -o weblog ./gorilla.go ./common.go

CMD ./weblog

# Datadog setup
ENV DD_TRACE_SAMPLE_RATE=0
ENV DD_TRACE_DEBUG=true
ENV DD_LOGGING_RATE=0
ENV DD_APPSEC_WAF_TIMEOUT=1s
ENV DD_TAGS='key1:val1, aKey : aVal bKey:bVal cKey:'
