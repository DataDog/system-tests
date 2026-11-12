
FROM python:3.11-slim
ARG FRAMEWORK_VERSION

# install bin dependancies
RUN apt-get update && apt-get install -y curl

WORKDIR /app

RUN python -m pip install fastapi==0.89.1 anyio==4.14.2 uvicorn==0.20.0 h11==0.16.0 idna==3.19 opentelemetry-exporter-otlp==1.36.0 protobuf==6.33.6 grpcio==1.83.1 googleapis-common-protos==1.75.2 Deprecated==1.3.1 wrapt==1.17.3 py-spy==0.4.2
RUN if [ "$FRAMEWORK_VERSION" = "latest" ]; then \
        python -m pip install anthropic; \
    else \
        python -m pip install anthropic==$FRAMEWORK_VERSION; \
    fi
# The MCP helpers (anthropic.lib.tools.mcp, anthropic>=0.84.0) need mcp, which needs pydantic 2 and so a newer FastAPI.
# The whole layer is pinned: pydantic generates the MCP tool input schema, part of the recorded request bodies.
RUN if python -c "import importlib.util, sys; sys.exit(importlib.util.find_spec('anthropic.lib.tools.mcp') is None)"; then \
        python -m pip install mcp==1.30.0 fastapi==0.115.12 uvicorn==0.34.0 \
            pydantic==2.14.3 pydantic-core==2.50.4 pydantic-settings==2.16.2 typing-inspection==0.4.5 annotated-types==0.8.0 \
            starlette==0.46.2 sse-starlette==3.0.3 httpx-sse==0.4.3 python-multipart==0.0.33 python-dotenv==1.2.4 \
            jsonschema==4.26.0 jsonschema-specifications==2025.9.1 referencing==0.37.0 rpds-py==2026.9.1 attrs==26.1.0 \
            PyJWT==2.15.1 cryptography==50.0.2 cffi==2.1.1 pycparser==3.12; \
    fi

COPY utils/build/docker/python/anthropic_app/system_tests_library_version.sh system_tests_library_version.sh
COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/

RUN /binaries/install_ddtrace.sh
RUN mkdir /integration-framework-tracer-logs

CMD ["ddtrace-run", "python", "-m", "integration_frameworks", "anthropic"]
