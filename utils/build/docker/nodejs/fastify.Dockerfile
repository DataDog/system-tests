FROM datadog/system-tests:fastify.base-v4

COPY utils/build/docker/nodejs/fastify/debugger debugger

EXPOSE 7777

ENV PGUSER=system_tests_user
ENV PGPASSWORD=system_tests
ENV PGDATABASE=system_tests_dbname
ENV PGHOST=postgres
ENV PGPORT=5433

ENV DD_DATA_STREAMS_ENABLED=true

# Refresh the application code and dependencies baked into the base image.
COPY utils/build/docker/nodejs/fastify/package.json utils/build/docker/nodejs/fastify/bun.lock ./
COPY utils/build/docker/nodejs/fastify/app.js app.js
RUN bun install --frozen-lockfile --network-concurrency 8 --linker=hoisted

# docker startup
COPY utils/build/docker/nodejs/app.sh app.sh
RUN chmod +x app.sh
RUN printf 'node app.js' >> app.sh
CMD ./app.sh

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh && rm -rf /root/.bun
ENV DD_TRACE_HEADER_TAGS=user-agent
