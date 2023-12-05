FROM python:2.7

# print versions
RUN python --version && curl --version

# install hello world app
RUN pip install pylons
COPY utils/build/docker/python/pylons/app /app

COPY utils/build/docker/python/install_ddtrace.sh utils/build/docker/python/get_appsec_rules_version.py binaries* /binaries/
RUN /binaries/install_ddtrace.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV _DD_APPSEC_DEDUPLICATION_ENABLED=false

# docker startup
RUN echo '#!/bin/bash \n\
cd /app && paster serve development.ini' > /app.sh
RUN chmod +x /app.sh
CMD ./app.sh

# docker build -f utils/build/docker/python.flask-poc.Dockerfile -t test .
# docker run -ti -p 7777:7777 test

