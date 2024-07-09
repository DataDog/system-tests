FROM datadog/system-tests:flask-poc.base-v1

WORKDIR /app

COPY binaries* /binaries/

COPY utils/build/docker/python/flask /app
COPY utils/build/docker/python_otel/flask-poc-otel/app.py /app
COPY utils/build/docker/python_otel/flask-poc-otel/app.sh /app

#TODO RMM: Change docker flask-poc base to fix psycopg2 ( psycopg2-binary is not supported by open telemetry)
RUN apt update
RUN apt install -y libpq-dev python3-dev git

RUN pip uninstall -y psycopg2-binary
RUN pip install psycopg2
#############

#Set opentelemetry-distro to 0.42b0 due this bug: https://github.com/open-telemetry/opentelemetry-python-contrib/issues/2046
# RUN pip install opentelemetry-distro==0.42b0 opentelemetry-exporter-otlp

RUN git clone https://github.com/open-telemetry/opentelemetry-python.git

WORKDIR /app/opentelemetry-python

RUN pip install ./opentelemetry-api
RUN pip install ./opentelemetry-semantic-conventions
RUN pip install ./opentelemetry-sdk

WORKDIR /app

RUN git clone https://github.com/open-telemetry/opentelemetry-python-contrib.git

WORKDIR /app/opentelemetry-python-contrib

RUN pip install ./opentelemetry-instrumentation
RUN pip install ./opentelemetry-distro
RUN pip install ./instrumentation/opentelemetry-instrumentation-confluent-kafka
RUN pip install ./util/opentelemetry-util-http
RUN pip install ./instrumentation/opentelemetry-instrumentation-wsgi
RUN pip install ./instrumentation/opentelemetry-instrumentation-flask
RUN pip install ./instrumentation/opentelemetry-instrumentation-botocore

# RUN pip install opentelemetry-exporter-otlp

WORKDIR /app

RUN opentelemetry-bootstrap -a install

RUN pip install ddtrace

# Install normal libs
RUN pip install confluent-kafka==2.1.1
RUN pip install boto3

RUN pip show opentelemetry-distro | grep Version: | cut -d' ' -f2 > SYSTEM_TESTS_LIBRARY_VERSION
RUN echo "1.0.0" > SYSTEM_TESTS_LIBDDWAF_VERSION
RUN echo "1.0.0" > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION

ENV DD_TRACE_OTEL_ENABLED=true
# ENV OTEL_TRACES_SAMPLER=always_on
ENV OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true
ENV FLASK_APP=app.py
CMD ./app.sh

