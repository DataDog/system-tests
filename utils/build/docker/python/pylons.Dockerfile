FROM python:2.7

# print versions
RUN python --version && curl --version

# install hello world app
RUN pip install pylons
COPY pylons/app /app

COPY ./install_ddtrace.sh ./get_appsec_rules_version.py binaries* /binaries/
RUN /binaries/install_ddtrace.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'

# docker startup
RUN echo '#!/bin/bash \n\
paster serve development.ini' > /app.sh
RUN chmod +x /app.sh
CMD ./app.sh

# docker build -f utils/build/docker/python.flask-poc.Dockerfile -t test .
# docker run -ti -p 7777:7777 test

