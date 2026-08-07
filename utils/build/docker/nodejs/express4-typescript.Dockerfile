FROM system_tests_base_nodejs_express4_typescript

EXPOSE 7777

ENV PGUSER=system_tests_user
ENV PGPASSWORD=system_tests
ENV PGDATABASE=system_tests_dbname
ENV PGHOST=postgres
ENV PGPORT=5433

ENV DD_DATA_STREAMS_ENABLED=true

# Refresh the application code and dependencies baked into the base image.
COPY utils/build/docker/nodejs/express4-typescript/package.json utils/build/docker/nodejs/express4-typescript/bun.lock ./
COPY utils/build/docker/nodejs/express4-typescript/app.ts app.ts
RUN bun install --frozen-lockfile --network-concurrency 8 --linker=hoisted

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh && rm -rf /root/.bun
RUN bun run build

# docker startup
COPY utils/build/docker/nodejs/app.sh app.sh
RUN printf 'node dist/app.js' >> app.sh
CMD ./app.sh
ENV DD_TRACE_HEADER_TAGS=user-agent

# docker build -f utils/build/docker/nodejs/express4-typescript.Dockerfile -t test .
# docker run -ti -p 7777:7777 test
