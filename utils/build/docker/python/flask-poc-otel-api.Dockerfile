FROM datadog/system-tests:flask-poc.base-v14

WORKDIR /app

COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

COPY utils/build/docker/python/flask-poc-otel-api/app.py /app/app.py
COPY utils/build/docker/python/flask-poc-otel-api/app.sh /app/app.sh
RUN chmod +x /app/app.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_REMOTECONFIG_POLL_SECONDS=1
ENV DD_DATA_STREAMS_ENABLED=True
ENV _DD_APPSEC_DEDUPLICATION_ENABLED=false
ENV DD_TRACE_OTEL_ENABLED=true

ENV FLASK_APP=app.py
CMD ./app.sh
