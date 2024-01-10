
FROM golang:1.20
# install jq
RUN apt-get update && apt-get -y install jq

WORKDIR /app

COPY ./utils/build/docker/golang/parametric/go.mod /app
COPY ./utils/build/docker/golang/parametric/go.sum /app
COPY ./utils/build/docker/golang/parametric/ /app
RUN go mod download && go mod verify

# download the proper tracer version
COPY utils/build/docker/golang/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
CMD cat SYSTEM_TESTS_LIBRARY_VERSION
