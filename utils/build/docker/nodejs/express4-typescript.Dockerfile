FROM node:18-alpine

RUN apk add --no-cache bash curl git jq
COPY --from=oven/bun:1.3.13-alpine /usr/local/bin/bun /usr/local/bin/bun

RUN uname -r

# print versions
RUN node --version && npm --version && bun --version && curl --version

WORKDIR /usr/app

COPY utils/build/docker/nodejs/express4-typescript /usr/app
RUN bun install --frozen-lockfile --linker=hoisted --network-concurrency 8

EXPOSE 7777

ENV PGUSER=system_tests_user
ENV PGPASSWORD=system_tests
ENV PGDATABASE=system_tests_dbname
ENV PGHOST=postgres
ENV PGPORT=5433

ENV DD_DATA_STREAMS_ENABLED=true

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
RUN bun run build

# docker startup
COPY utils/build/docker/nodejs/app.sh app.sh
RUN printf 'node dist/app.js' >> app.sh
CMD ./app.sh
ENV DD_TRACE_HEADER_TAGS=user-agent

# docker build -f utils/build/docker/nodejs.datadog.Dockerfile -t test .
# docker run -ti -p 7777:7777 test
