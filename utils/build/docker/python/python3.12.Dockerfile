FROM datadog/system-tests:python3.12.base-v1

WORKDIR /app

COPY utils/build/docker/python/install_ddtrace.sh utils/build/docker/python/get_appsec_rules_version.py binaries* /binaries/
RUN /binaries/install_ddtrace.sh

COPY utils/build/docker/python/django/app.sh /app/app.sh
COPY utils/build/docker/python/django/django.app.urls.py /app/app/urls.py
COPY utils/build/docker/python/iast.py /app/iast.py

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_REMOTECONFIG_POLL_SECONDS=1
ENV _DD_APPSEC_DEDUPLICATION_ENABLED=false

# docker startup
CMD ./app.sh

# docker build -f utils/build/docker/python/django-poc.Dockerfile -t test .
# docker run -ti -p 7777:7777 test
