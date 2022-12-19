FROM python:3.9

# print versions
RUN python --version && curl --version

# install hello world app
RUN pip install flask gunicorn gevent requests psycopg2

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
CMD ./app.sh

# docker build -f utils/build/docker/python.flask-poc.Dockerfile -t test .
# docker run -ti -p 7777:7777 test

