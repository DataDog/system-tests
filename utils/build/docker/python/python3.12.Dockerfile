FROM datadog/system-tests:python3.12.base-v8

WORKDIR /app

COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

COPY utils/build/docker/python/django /app
COPY utils/build/docker/python/iast.py /app/iast.py

RUN python manage.py makemigrations
RUN python manage.py migrate
RUN DJANGO_SUPERUSER_PASSWORD=abcd python3 manage.py createsuperuser --noinput --username root --email root@n0wh3re.net


ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_REMOTECONFIG_POLL_SECONDS=1
ENV _DD_APPSEC_DEDUPLICATION_ENABLED=false

# docker startup
CMD ./app.sh

# docker build -f utils/build/docker/python/django-poc.Dockerfile -t test .
# docker run -ti -p 7777:7777 test
