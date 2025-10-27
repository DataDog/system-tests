
FROM python:3.11-slim
ARG FRAMEWORK_VERSION

# install bin dependancies
RUN apt-get update && apt-get install -y curl

WORKDIR /app

RUN python -m pip install fastapi==0.89.1 uvicorn==0.20.0 opentelemetry-exporter-otlp==1.36.0
RUN python -m pip install openai==$FRAMEWORK_VERSION

COPY utils/build/docker/python/openai_app/system_tests_library_version.sh system_tests_library_version.sh
COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/

RUN /binaries/install_ddtrace.sh
RUN mkdir /integration-framework-tracer-logs

ENV DD_PATCH_MODULES="fastapi:false,starlette:false"
ENV OPENAI_API_KEY="<not-a-real-key>"
CMD ["ddtrace-run", "python", "-m", "integration_frameworks", "openai"]
