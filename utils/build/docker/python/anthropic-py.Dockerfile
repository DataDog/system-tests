
FROM python:3.11-slim
ARG FRAMEWORK_VERSION

# install bin dependancies
RUN apt-get update && apt-get install -y curl

WORKDIR /app

RUN python -m pip install fastapi==0.89.1 anyio==4.14.2 uvicorn==0.20.0 h11==0.16.0 idna==3.19 opentelemetry-exporter-otlp==1.36.0 protobuf==6.33.6 grpcio==1.83.1 googleapis-common-protos==1.75.2 Deprecated==1.3.1 wrapt==1.17.3
RUN if [ "$FRAMEWORK_VERSION" = "latest" ]; then \
        python -m pip install anthropic; \
    else \
        python -m pip install anthropic==$FRAMEWORK_VERSION; \
    fi

COPY utils/build/docker/python/anthropic_app/system_tests_library_version.sh system_tests_library_version.sh
COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/

RUN /binaries/install_ddtrace.sh
RUN mkdir /integration-framework-tracer-logs

CMD ["ddtrace-run", "python", "-m", "integration_frameworks", "anthropic"]
