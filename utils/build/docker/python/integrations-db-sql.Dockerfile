FROM datadog/system-tests:flask-poc.base-v0

COPY utils/build/docker/python/integrations-db-sql /app
WORKDIR /app

COPY utils/build/docker/python/install_ddtrace.sh utils/build/docker/python/get_appsec_rules_version.py binaries* /binaries/
RUN /binaries/install_ddtrace.sh

#DRIVER MSSQL
RUN apt-get update && apt-get install -y unixodbc gnupg2

RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -

RUN curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list

RUN apt-get update

RUN ACCEPT_EULA=Y apt-get install -y msodbcsql17
RUN pip install pymysql cryptography pyodbc

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_REMOTECONFIG_POLL_SECONDS=1

ENV DD_DATA_STREAMS_ENABLED=true
ENV DD_TRACE_SPAN_ATTRIBUTE_SCHEMA="v1"

# docker startup
# FIXME: Ensure gevent patching occurs before ddtrace

#RUN echo "********************* EL DRIVER ********************"
#RUN odbcinst -j
#RUN echo "********************* FIN DEL DRIVER ********************"


ENV FLASK_APP=app.py
CMD ./app.sh

# docker build -f utils/build/docker/python/flask-poc.Dockerfile -t test .
# docker run -ti -p 7777:7777 test
