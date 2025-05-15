FROM datadog/system-tests:flask-poc.base-v9

WORKDIR /app

COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

COPY utils/build/docker/python/flask /app
COPY utils/build/docker/python/iast.py /app/iast.py

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_REMOTECONFIG_POLL_SECONDS=1
ENV DD_DATA_STREAMS_ENABLED=True
ENV _DD_APPSEC_DEDUPLICATION_ENABLED=false
ENV DD_IAST_VULNERABILITIES_PER_REQUEST=5

# docker startup
# FIXME: Ensure gevent patching occurs before ddtrace

ENV FLASK_APP=app.py

ENV DD_APM_RECEIVER_SOCKET=/var/run/datadog/apm.socket
RUN apt-get update && apt-get install socat -y
ENV UDS_WEBLOG=1
COPY utils/build/docker/set-uds-transport.sh set-uds-transport.sh

CMD ./app.sh

# docker build -f utils/build/docker/python.flask-poc.Dockerfile -t test .
# docker run -ti -p 7777:7777 test

