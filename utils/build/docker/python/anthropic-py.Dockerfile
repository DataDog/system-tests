
FROM python:3.11-slim
ARG FRAMEWORK_VERSION

# install bin dependancies
RUN apt-get update && apt-get install -y curl

WORKDIR /app

RUN python -m pip install fastapi==0.89.1 uvicorn==0.20.0 opentelemetry-exporter-otlp==1.36.0
RUN if [ "$FRAMEWORK_VERSION" = "latest" ]; then \
        python -m pip install anthropic; \
    else \
        python -m pip install anthropic==$FRAMEWORK_VERSION; \
    fi

COPY utils/build/docker/python/anthropic_app/system_tests_library_version.sh system_tests_library_version.sh
COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/

RUN /binaries/install_ddtrace.sh

# py-spy lets system-tests dump this weblog's thread stacks from outside the
# process when a remote config apply stalls (see utils/_remote_config.py)
RUN pip install py-spy==0.4.1
RUN mkdir /integration-framework-tracer-logs

CMD ["ddtrace-run", "python", "-m", "integration_frameworks", "anthropic"]
