FROM golang:1

# print versions
RUN go version && curl --version

COPY utils/build/docker/golang/install_ddtrace.sh binaries* /binaries/
COPY utils/build/docker/golang/app /app

WORKDIR /app

RUN /binaries/install_ddtrace.sh

RUN go build -v -tags appsec -o weblog ./gin.go ./common.go

RUN echo "#!/bin/bash\n./weblog" > ./app.sh
RUN chmod +x app.sh
CMD ["./app.sh"]

# Datadog setup
ENV DD_LOGGING_RATE=0
