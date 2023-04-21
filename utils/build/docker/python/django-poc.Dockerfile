FROM python:3.9

# print versions
RUN python --version && curl --version

# install hello world app
RUN pip install django pycryptodome gunicorn gevent requests

RUN mkdir app
RUN django-admin startproject django_app app
WORKDIR /app
RUN python3 manage.py startapp app

RUN sed -i "1s/^/from django.urls import include\n/" django_app/urls.py
RUN sed -i "s/admin\///g" django_app/urls.py
RUN sed -i "s/admin.site.urls/include(\"app.urls\")/g" django_app/urls.py
RUN sed -i "s/ALLOWED_HOSTS\s=\s\[\]/ALLOWED_HOSTS = \[\"0.0.0.0\",\"weblog\"\,\"localhost\"\]/g" django_app/settings.py

COPY utils/build/docker/python/django/app.sh /app/app.sh
COPY utils/build/docker/python/django/django.app.urls.py /app/app/urls.py
COPY utils/build/docker/python/iast.py /app/iast.py


COPY utils/build/docker/python/install_ddtrace.sh utils/build/docker/python/get_appsec_rules_version.py binaries* /binaries/
RUN /binaries/install_ddtrace.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_REMOTECONFIG_POLL_SECONDS=1

# docker startup
CMD ./app.sh

# docker build -f utils/build/docker/python/django-poc.Dockerfile -t test .
# docker run -ti -p 7777:7777 test
