FROM python:3.9

# print versions
RUN python --version && curl --version

# install hello world app
# Tracer does not support flask 2.3.0 or higher, pin the flask version for now
RUN pip install flask==2.2.4 gunicorn gevent requests pycryptodome psycopg2

COPY utils/build/docker/python/flask /app
COPY utils/build/docker/python/iast.py /app/iast.py
WORKDIR /app

COPY utils/build/docker/python/install_ddtrace.sh utils/build/docker/python/get_appsec_rules_version.py binaries* /binaries/
RUN /binaries/install_ddtrace.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_REMOTECONFIG_POLL_SECONDS=1

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

