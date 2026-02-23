FROM datadog/system-tests:tornado.base-v2

WORKDIR /app

ENV DD_TRACE_TORNADO_ENABLED=true

COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

COPY utils/build/docker/python/tornado/app.sh /app/app.sh
COPY utils/build/docker/python/tornado/main.py /app/main.py
COPY utils/build/docker/python/iast.py /app/iast.py

# docker startup
CMD ./app.sh

# docker build -f utils/build/docker/python/tornado.Dockerfile -t test .
# docker run -ti -p 7777:7777 test
