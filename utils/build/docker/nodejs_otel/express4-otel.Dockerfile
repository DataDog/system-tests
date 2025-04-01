FROM node:18-alpine

RUN apk add --no-cache bash curl git jq

RUN uname -r

# print versions
RUN node --version && npm --version && curl --version

COPY utils/build/docker/nodejs/express /usr/app
#overwrite app.js
COPY utils/build/docker/nodejs_otel/express4-otel /usr/app

WORKDIR /usr/app

ENV NODE_ENV=production

RUN npm install || npm install
RUN npm install "express@4.17.2" "apollo-server-express@3.13.0" "express-mongo-sanitize@2.2.0" \
  || npm install "express@4.17.2" "apollo-server-express@3.13.0" "express-mongo-sanitize@2.2.0"

EXPOSE 7777

ENV PGUSER=system_tests_user
ENV PGPASSWORD=system_tests
ENV PGDATABASE=system_tests_dbname
ENV PGHOST=postgres
ENV PGPORT=5433

#ENV OTEL_BSP_MAX_QUEUE_SIZE=10000
ENV OTEL_BSP_EXPORT_TIMEOUT=1000
ENV OTEL_BSP_SCHEDULE_DELAY=200
RUN npm install --save @opentelemetry/api || npm install --save @opentelemetry/api
RUN npm install --save @opentelemetry/auto-instrumentations-node \
  || npm install --save @opentelemetry/auto-instrumentations-node
RUN npm install @opentelemetry/instrumentation-mysql2 || npm install @opentelemetry/instrumentation-mysql2
RUN npm install @opentelemetry/otlp-exporter-base || npm install @opentelemetry/otlp-exporter-base
RUN npm install --save opentelemetry-instrumentation-mssql || npm install --save opentelemetry-instrumentation-mssql

# docker startup
COPY utils/build/docker/nodejs/app.sh app.sh
RUN printf 'node --require @opentelemetry/auto-instrumentations-node/register app.js' >> app.sh
CMD ./app.sh
