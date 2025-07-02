FROM datadog/system-tests:uwsgi-poc.base-v6

WORKDIR /app

COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

COPY utils/build/docker/python/flask /app
COPY utils/build/docker/python/iast.py /app/iast.py
ENV FLASK_APP=app.py

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_REMOTECONFIG_POLL_SECONDS=1
ENV DD_DATA_STREAMS_ENABLED=True
ENV _DD_APPSEC_DEDUPLICATION_ENABLED=false
ENV UWSGI_ENABLED=true
ENV DD_TESTING_RAISE=true
ENV DD_REMOTE_CONFIGURATION_ENABLED=false
ENV DD_DYNAMIC_INSTRUMENTATION_ENABLED=false
ENV DD_IAST_ENABLED=false

# docker startup
# note, only thread mode is supported
# https://ddtrace.readthedocs.io/en/stable/advanced_usage.html#uwsgi
RUN echo '#!/bin/bash \n\
uwsgi -p 1 --enable-threads --threads 2 --listen 100 --http :7777 -w app:app --lazy --lazy-apps --import=ddtrace.bootstrap.sitecustomize\n' > app.sh
RUN chmod +x app.sh
CMD ./app.sh

# docker build -f utils/build/docker/python.flask-poc.Dockerfile -t test .
# docker run -ti -p 7777:7777 test

