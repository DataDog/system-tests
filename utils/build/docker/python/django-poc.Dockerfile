FROM python:3.9

# print versions
RUN python --version && curl --version

# install hello world app
RUN pip install django requests


RUN django-admin startproject django_app .
RUN python3 manage.py startapp app

RUN sed -i "1s/^/from django.urls import include\n/" django_app/urls.py
RUN sed -i "s/admin\///g" django_app/urls.py
RUN sed -i "s/admin.site.urls/include(\"app.urls\")/g" django_app/urls.py
RUN sed -i "s/ALLOWED_HOSTS\s=\s\[\]/ALLOWED_HOSTS = \[\"0.0.0.0\",\"weblog\"\]/g" django_app/settings.py

COPY utils/build/docker/python/django.app.urls.py /app/urls.py

COPY utils/build/docker/python/install_ddtrace.sh utils/build/docker/python/get_appsec_rules_version.py binaries* /binaries/
RUN /binaries/install_ddtrace.sh

# docker startup
RUN echo '#!/bin/bash \n\
ddtrace-run python manage.py runserver 0.0.0.0:7777\n' > /app.sh
RUN chmod +x /app.sh
CMD ./app.sh

# docker build -f utils/build/docker/python/django-poc.Dockerfile -t test .
# docker run -ti -p 7777:7777 test
