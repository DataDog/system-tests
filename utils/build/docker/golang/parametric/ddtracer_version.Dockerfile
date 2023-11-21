
FROM golang:1.20
WORKDIR /client

COPY ./utils/build/docker/golang/parametric/go.mod /client
COPY ./utils/build/docker/golang/parametric/go.sum /client
COPY ./utils/build/docker/golang/parametric/ /client
COPY ./utils/build/docker/golang/parametric/ddtracer_version.sh .
RUN sh ddtracer_version.sh
CMD cat SYSTEM_TESTS_LIBRARY_VERSION
