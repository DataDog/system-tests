FROM node:18-slim

RUN apt-get update && apt-get install -y jq curl

RUN uname -r

# print versions
RUN node --version && npm --version && curl --version

COPY utils/build/docker/nodejs/express4 /usr/app

WORKDIR /usr/app

RUN npm install

EXPOSE 7777

ENV PGUSER=system_tests_user
ENV PGPASSWORD=system_tests
ENV PGDATABASE=system_tests_dbname
ENV PGHOST=postgres
ENV PGPORT=5433

ENV DD_APM_RECEIVER_SOCKET=/var/run/datadog/apm.socket
ENV UDS_WEBLOG=1

ENV DD_DATA_STREAMS_ENABLED=true

# docker startup
COPY utils/build/docker/nodejs/app.sh app.sh
COPY utils/build/docker/set-uds-transport.sh set-uds-transport.sh
CMD ./app.sh

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
ENV DD_TRACE_HEADER_TAGS=user-agent
