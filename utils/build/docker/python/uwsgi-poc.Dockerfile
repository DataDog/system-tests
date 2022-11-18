FROM python:3.9

# print versions
RUN python --version && curl --version

# install hello world app
RUN pip install flask uwsgi requests

COPY utils/build/docker/python/flask.py app.py
ENV FLASK_APP=app.py

COPY utils/build/docker/python/install_ddtrace.sh utils/build/docker/python/get_appsec_rules_version.py binaries* /binaries/
RUN /binaries/install_ddtrace.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_REMOTECONFIG_POLL_SECONDS=1

# docker startup
# note, only thread mode is supported
# https://ddtrace.readthedocs.io/en/stable/advanced_usage.html#uwsgi
RUN echo '#!/bin/bash \n\
ddtrace-run uwsgi --http :7777 -w app:app --enable-threads\n' > /app.sh
RUN chmod +x /app.sh
CMD ./app.sh

# docker build -f utils/build/docker/python.flask-poc.Dockerfile -t test .
# docker run -ti -p 7777:7777 test

