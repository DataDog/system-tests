FROM system_tests_base_python_aiohttp

WORKDIR /app

COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

# Install OTel OTLP exporter for FFE metrics
RUN pip install opentelemetry-exporter-otlp-proto-http==1.40.0

COPY utils/build/docker/python/aiohttp/app.sh /app/app.sh
COPY utils/build/docker/python/aiohttp/main.py /app/main.py
COPY utils/build/docker/python/iast.py /app/iast.py

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_REMOTECONFIG_POLL_SECONDS=1
ENV _DD_APPSEC_DEDUPLICATION_ENABLED=false

# docker startup
CMD ./app.sh

# docker build -f utils/build/docker/python/aiohttp.Dockerfile -t test .
# docker run -ti -p 7777:7777 test
