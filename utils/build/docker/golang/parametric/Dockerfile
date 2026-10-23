
FROM golang:1.26

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

RUN if go doc github.com/DataDog/dd-trace-go/v2/openfeature.NewExposureHook >/dev/null 2>&1; then \
      go install -tags=dd_exposure_hook; \
    else go install; fi

CMD ["sh", "-c", "main; status=$?; sleep 2; exit $status"]
