
FROM ghcr.io/datadog/dd-trace-py/testrunner:bca6869fffd715ea9a731f7b606807fa1b75cb71
WORKDIR /app
RUN pyenv global 3.11
RUN python3.11 -m pip install fastapi==0.89.1 uvicorn==0.20.0 opentelemetry-exporter-otlp==1.36.0 openfeature-sdk==0.8.3
COPY utils/build/docker/python/parametric/system_tests_library_version.sh system_tests_library_version.sh
COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
RUN mkdir /parametric-tracer-logs
ENV DD_PATCH_MODULES="fastapi:false,startlette:false"

CMD ["ddtrace-run", "python3.11", "-m", "apm_test_client"]