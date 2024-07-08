FROM datadog/system-tests:fastapi.base-v1

WORKDIR /app

COPY utils/build/docker/python/install_ddtrace.sh utils/build/docker/python/get_appsec_rules_version.py binaries* /binaries/
RUN /binaries/install_ddtrace.sh
RUN python3.10 -m pip install --upgrade pip
RUN python3.10 -m pip install PyYAML uvicorn requests psycopg2-binary python-multipart

COPY utils/build/docker/python/fastapi/app.sh /app/app.sh
COPY utils/build/docker/python/fastapi/main.py /app/main.py
COPY utils/build/docker/python/fastapi/log_conf.yaml /app/log_conf.yaml
COPY utils/build/docker/python/iast.py /app/iast.py

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_REMOTECONFIG_POLL_SECONDS=1
ENV _DD_APPSEC_DEDUPLICATION_ENABLED=false

# docker startup
CMD ./app.sh

# docker build -f utils/build/docker/python/fastapi.Dockerfile -t test .
# docker run -ti -p 7777:7777 test
