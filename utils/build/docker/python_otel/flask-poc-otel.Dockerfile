FROM datadog/system-tests:flask-poc.base-v1

WORKDIR /app

COPY binaries* /binaries/
RUN echo "1.0.0" > SYSTEM_TESTS_LIBRARY_VERSION
RUN echo "1.0.0" > SYSTEM_TESTS_LIBDDWAF_VERSION
RUN echo "1.0.0" > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION

COPY utils/build/docker/python/flask /app
COPY utils/build/docker/python/iast.py /app/iast.py
COPY utils/build/docker/python_otel/flask-poc-otel/app.sh /app

RUN pip install opentelemetry-distro opentelemetry-exporter-otlp
RUN opentelemetry-bootstrap -a install

ENV FLASK_APP=app.py
CMD ./app.sh

