FROM datadog/system-tests:flask-poc.base-v11

#TODO RMM: Change docker flask-poc base to fix psycopg2 ( psycopg2-binary is not supported by open telemetry)
RUN apt update
RUN apt install -y libpq-dev python3-dev
RUN pip uninstall -y psycopg2-binary
RUN pip install psycopg2
#############

RUN pip install opentelemetry-distro[otlp]==0.49b0

WORKDIR /app
COPY binaries* /binaries/

COPY utils/build/docker/python/flask /app
COPY utils/build/docker/python_otel/flask-poc-otel/app.py /app
COPY utils/build/docker/python_otel/flask-poc-otel/app.sh /app

RUN opentelemetry-bootstrap -a install
RUN pip freeze | grep opentelemetry

ENV OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true
ENV FLASK_APP=app.py
CMD ./app.sh

