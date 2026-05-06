FROM node:18-alpine

RUN apk add --no-cache bash curl git jq

RUN uname -r

# print versions
RUN node --version && npm --version && curl --version

WORKDIR /usr/app

ENV NODE_ENV=production

COPY utils/build/docker/nodejs/express /usr/app
#overwrite app.js and package files
COPY utils/build/docker/nodejs_otel/express4-otel /usr/app
RUN npm ci || (sleep 30 && npm ci)

EXPOSE 7777

ENV PGUSER=system_tests_user
ENV PGPASSWORD=system_tests
ENV PGDATABASE=system_tests_dbname
ENV PGHOST=postgres
ENV PGPORT=5433

#ENV OTEL_BSP_MAX_QUEUE_SIZE=10000
ENV OTEL_BSP_EXPORT_TIMEOUT=1000
ENV OTEL_BSP_SCHEDULE_DELAY=200

# docker startup
COPY utils/build/docker/nodejs/app.sh app.sh
RUN printf 'node --require @opentelemetry/auto-instrumentations-node/register app.js' >> app.sh
CMD ./app.sh
