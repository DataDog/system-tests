FROM python:3.9

# print versions
RUN python --version && curl --version

# install hello world app
RUN pip install flask gunicorn gevent requests

COPY utils/build/docker/python/flask.py app.py
ENV FLASK_APP=app.py

COPY utils/build/docker/python/install_ddtrace.sh utils/build/docker/python/get_appsec_rules_version.py binaries* /binaries/
RUN /binaries/install_ddtrace.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_REMOTECONFIG_POLL_SECONDS=0.5

# docker startup
RUN echo '#!/bin/bash \n\
ddtrace-run gunicorn -w 2 -b 0.0.0.0:7777 --access-logfile - app:app -k gevent\n' > /app.sh
RUN chmod +x /app.sh
CMD ./app.sh

# docker build -f utils/build/docker/python.flask-poc.Dockerfile -t test .
# docker run -ti -p 7777:7777 test

