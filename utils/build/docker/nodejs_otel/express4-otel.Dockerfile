FROM datadog/system-tests:express4.base-v0

RUN uname -r
RUN node --version && npm --version && curl --version

COPY utils/build/docker/nodejs/express4 /usr/app
#overwrite app.js
COPY utils/build/docker/nodejs_otel/express4-otel /usr/app

RUN npm install

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
RUN printf '#!/bin/bash\nnode --require @opentelemetry/auto-instrumentations-node/register app.js' > app.sh
