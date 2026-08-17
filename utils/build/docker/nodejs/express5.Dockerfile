FROM datadog/system-tests:express5.base-v3

# Refresh the application code and dependencies baked into the base image.
COPY utils/build/docker/nodejs/express/app.js app.js
COPY utils/build/docker/nodejs/express/debugger debugger
COPY utils/build/docker/nodejs/express5/package.json utils/build/docker/nodejs/express5/bun.lock ./
RUN bun install --frozen-lockfile --network-concurrency 8 --linker=hoisted

EXPOSE 7777

ENV PGUSER=system_tests_user
ENV PGPASSWORD=system_tests
ENV PGDATABASE=system_tests_dbname
ENV PGHOST=postgres
ENV PGPORT=5433

ENV DD_DATA_STREAMS_ENABLED=true

# docker startup
COPY utils/build/docker/nodejs/app.sh app.sh
RUN chmod +x app.sh
RUN printf 'node app.js' >> app.sh
CMD ./app.sh

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh && rm -rf /root/.bun
ENV DD_TRACE_HEADER_TAGS=user-agent
