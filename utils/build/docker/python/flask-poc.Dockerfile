FROM python:3.9

# print versions
RUN python --version && curl --version

# install hello world app
RUN pip install flask gunicorn

COPY utils/build/docker/python/flask.py app.py
ENV FLASK_APP=app.py

COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

# Datadog setup
ENV DD_TRACE_SAMPLE_RATE=0.5
ENV DD_TAGS='key1:val1, key2 : val2 '

# docker startup
RUN echo '#!/bin/bash \n\
ddtrace-run gunicorn -w 2 -b 0.0.0.0:7777 --access-logfile - app:app \n' > /app.sh
RUN chmod +x /app.sh
CMD ./app.sh

# docker build -f utils/build/docker/python.flask-poc.Dockerfile -t test .
# docker run -ti -p 7777:7777 test

