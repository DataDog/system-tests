FROM golang:1.24

# print important lib versions
RUN go version && curl --version

# install jq
RUN apt-get update && apt-get -y install jq

# download go dependencies
RUN mkdir -p /app
COPY utils/build/docker/golang/app/go.mod utils/build/docker/golang/app/go.sum /app/
WORKDIR /app
RUN go mod download && go mod verify

# copy the app code
COPY utils/build/docker/golang/app /app

# download the proper tracer version
COPY utils/build/docker/golang/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
ENV DD_TRACE_HEADER_TAGS='user-agent'

RUN go build -v -tags appsec -o weblog ./graph-gophers

RUN echo "#!/bin/bash\nexec ./weblog" > app.sh
RUN chmod +x app.sh
CMD ["./app.sh"]

# Datadog setup
ENV DD_LOGGING_RATE=0
