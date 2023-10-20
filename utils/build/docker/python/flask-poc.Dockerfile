FROM datadog/system-tests:flask-poc.base-v1

WORKDIR /app

COPY utils/build/docker/python/install_ddtrace.sh utils/build/docker/python/get_appsec_rules_version.py binaries* /binaries/
RUN /binaries/install_ddtrace.sh

COPY utils/build/docker/python/flask /app
COPY utils/build/docker/python/iast.py /app/iast.py

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_REMOTECONFIG_POLL_SECONDS=1

# docker startup
# FIXME: Ensure gevent patching occurs before ddtrace

ENV FLASK_APP=app.py
RUN pip install flask-login
CMD ./app.sh

# docker build -f utils/build/docker/python/flask-poc.Dockerfile -t test .
# docker run -ti -p 7777:7777 test
