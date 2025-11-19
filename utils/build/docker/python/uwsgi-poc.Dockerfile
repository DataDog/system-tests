FROM datadog/system-tests:uwsgi-poc.base-v8

WORKDIR /app

COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
# TODO(munir): Move loguru install to the base image, currently lack permissions to push a new base image.
RUN pip install loguru==0.7.3

COPY utils/build/docker/python/flask /app
COPY utils/build/docker/python/iast.py /app/iast.py
ENV FLASK_APP=app.py

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_REMOTECONFIG_POLL_SECONDS=1
ENV DD_DATA_STREAMS_ENABLED=True
ENV _DD_APPSEC_DEDUPLICATION_ENABLED=false
ENV UWSGI_ENABLED=true

# docker startup
# note, only thread mode is supported
# https://ddtrace.readthedocs.io/en/stable/advanced_usage.html#uwsgi
RUN echo '#!/bin/bash \n\
echo "--- PIP FREEZE ---"\n\
python -m pip freeze\n\
echo "------------------"\n\
uwsgi --http :7777 -w app:app --threads 2 --enable-threads --skip-atexit --lazy-apps --import=ddtrace.bootstrap.sitecustomize\n' > app.sh
RUN chmod +x app.sh
CMD ./app.sh

# docker build -f utils/build/docker/python.flask-poc.Dockerfile -t test .
# docker run -ti -p 7777:7777 test

