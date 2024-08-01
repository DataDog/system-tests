FROM node:18-alpine

RUN apk add --no-cache bash curl git jq

RUN uname -r

# print versions
RUN node --version && npm --version && curl --version

COPY utils/build/docker/nodejs/express4 /usr/app
#overwrite app.js
COPY utils/build/docker/nodejs_otel/express4-otel /usr/app

WORKDIR /usr/app

ENV NODE_ENV=production

RUN npm install

EXPOSE 7777

ENV PGUSER=system_tests_user
ENV PGPASSWORD=system_tests
ENV PGDATABASE=system_tests_dbname
ENV PGHOST=postgres
ENV PGPORT=5433

#ENV OTEL_BSP_MAX_QUEUE_SIZE=10000
ENV OTEL_BSP_EXPORT_TIMEOUT=1000
ENV OTEL_BSP_SCHEDULE_DELAY=200
RUN npm install --save @opentelemetry/api
RUN npm install --save @opentelemetry/auto-instrumentations-node
RUN npm install @opentelemetry/instrumentation-mysql2
RUN npm install --save opentelemetry-instrumentation-mssql

RUN npm list --json | jq -r '.dependencies."@opentelemetry/auto-instrumentations-node".version' > SYSTEM_TESTS_LIBRARY_VERSION
RUN printf "1.0.0" > SYSTEM_TESTS_LIBDDWAF_VERSION
RUN printf "1.0.0" > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION

# docker startup
COPY utils/build/docker/nodejs/app.sh app.sh
RUN printf '#!/bin/bash\nnode --require @opentelemetry/auto-instrumentations-node/register app.js' > server.sh
RUN chmod +x server.sh
CMD ./app.sh