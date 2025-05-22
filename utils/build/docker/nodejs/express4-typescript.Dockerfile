FROM node:18-alpine

RUN apk add --no-cache bash curl git jq

RUN uname -r

# print versions
RUN node --version && npm --version && curl --version

COPY utils/build/docker/nodejs/express4-typescript /usr/app

WORKDIR /usr/app


EXPOSE 7777

ENV PGUSER=system_tests_user
ENV PGPASSWORD=system_tests
ENV PGDATABASE=system_tests_dbname
ENV PGHOST=postgres
ENV PGPORT=5433

ENV DD_DATA_STREAMS_ENABLED=true

ENV DD_IAST_MAX_CONTEXT_OPERATIONS=10

# docker startup
COPY utils/build/docker/nodejs/app.sh app.sh
RUN printf 'node dist/app.js' >> app.sh
CMD ./app.sh

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/

RUN npm install || npm install
RUN /binaries/install_ddtrace.sh
RUN npm run build
ENV DD_TRACE_HEADER_TAGS=user-agent

# docker build -f utils/build/docker/nodejs.datadog.Dockerfile -t test .
# docker run -ti -p 7777:7777 test
