
FROM system_tests_base_python_python_parametric

# BuildKit's docker-container driver (used in GitLab CI) injects OTEL_TRACES_EXPORTER=otlp and a unix:// gRPC
# endpoint into RUN steps. Tracers honoring it can fail at build time. ARG only applies at build time.
ARG OTEL_TRACES_EXPORTER=none

WORKDIR /app
COPY utils/build/docker/python/parametric/system_tests_library_version.sh system_tests_library_version.sh
COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
RUN mkdir /parametric-tracer-logs
ENV DD_PATCH_MODULES="fastapi:false,starlette:false"

CMD ["ddtrace-run", "python3.11", "-m", "apm_test_client"]