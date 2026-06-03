FROM datadog/system-tests:express4-typescript.base-v2

COPY utils/build/docker/nodejs/express4-typescript /usr/app

EXPOSE 7777

ENV PGUSER=system_tests_user
ENV PGPASSWORD=system_tests
ENV PGDATABASE=system_tests_dbname
ENV PGHOST=postgres
ENV PGPORT=5433

ENV DD_DATA_STREAMS_ENABLED=true

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
