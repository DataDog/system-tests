FROM python:3.11-slim

# BuildKit's docker-container driver (used in GitLab CI) injects OTEL_TRACES_EXPORTER=otlp and a unix:// gRPC
# endpoint into RUN steps. Tracers honoring it can fail at build time. ARG only applies at build time.
ARG OTEL_TRACES_EXPORTER=none

ARG FRAMEWORK_VERSION

# Use the model cost map that litellm ships, so that litellm does not download it at import time.
ENV LITELLM_LOCAL_MODEL_COST_MAP=True

# install bin dependancies
RUN apt-get update && apt-get install -y curl

WORKDIR /app

RUN python -m pip install fastapi==0.100.0 anyio==4.14.2 uvicorn==0.20.0 h11==0.16.0 idna==3.19 py-spy==0.4.2
# A pinned litellm version also gets a pinned openai version, because litellm does not set an upper bound on it.
RUN if [ "$FRAMEWORK_VERSION" = "latest" ]; then \
        python -m pip install --retries 10 --timeout 120 litellm; \
    else \
        python -m pip install --retries 10 --timeout 120 litellm==$FRAMEWORK_VERSION openai==2.30.0; \
    fi

COPY utils/build/docker/python/litellm_app/system_tests_library_version.sh system_tests_library_version.sh
COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/

RUN /binaries/install_ddtrace.sh
RUN mkdir /integration-framework-tracer-logs

CMD ["ddtrace-run", "python", "-m", "integration_frameworks", "litellm"]
