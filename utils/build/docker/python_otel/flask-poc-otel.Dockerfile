FROM datadog/system-tests:flask-poc.base-v1

WORKDIR /app
RUN echo "hola"
COPY binaries* /binaries/

COPY utils/build/docker/python/flask /app
COPY utils/build/docker/python_otel/flask-poc-otel/app.py /app
COPY utils/build/docker/python_otel/flask-poc-otel/app.sh /app

#TODO RMM: Change docker flask-poc base to fix psycopg2 ( psycopg2-binary is not supported by open telemetry)
RUN apt update
RUN apt install -y libpq-dev python3-dev
RUN pip uninstall -y psycopg2-binary
RUN pip install psycopg2
#############

RUN pip install opentelemetry-distro==0.47b0 opentelemetry-exporter-otlp

RUN opentelemetry-bootstrap -a install

RUN pip show opentelemetry-distro | grep Version: | cut -d' ' -f2 > SYSTEM_TESTS_LIBRARY_VERSION
RUN echo "1.0.0" > SYSTEM_TESTS_LIBDDWAF_VERSION
RUN echo "1.0.0" > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION

ENV OTEL_LOG_LEVEL="debug"
ENV OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true
ENV FLASK_APP=app.py
CMD ./app.sh

