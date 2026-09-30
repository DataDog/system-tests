
FROM python:3.11-slim
WORKDIR /app
RUN python3.11 -m pip install fastapi==0.89.1 anyio==4.14.2 uvicorn==0.20.0 h11==0.16.0 idna==3.19 opentelemetry-exporter-otlp==1.36.0 protobuf==6.33.6 grpcio==1.83.1 googleapis-common-protos==1.75.2 Deprecated==1.3.1 wrapt==1.17.3 openfeature-sdk==0.8.3
COPY utils/build/docker/python/parametric/system_tests_library_version.sh system_tests_library_version.sh
COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
RUN mkdir /parametric-tracer-logs
ENV DD_PATCH_MODULES="fastapi:false,starlette:false"

CMD ["ddtrace-run", "python3.11", "-m", "apm_test_client"]