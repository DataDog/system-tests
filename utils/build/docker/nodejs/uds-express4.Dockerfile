FROM datadog/system-tests:express4.base-v3

# The base image bakes in app.js; refresh it (and fork_child.js, which is loaded via a
# runtime path so it is never bundled) so the /spawn_child endpoint is present.
COPY utils/build/docker/nodejs/express/app.js app.js
COPY utils/build/docker/nodejs/express/fork_child.js fork_child.js
COPY utils/build/docker/nodejs/express/debugger debugger

EXPOSE 7777

ENV PGUSER=system_tests_user
ENV PGPASSWORD=system_tests
ENV PGDATABASE=system_tests_dbname
ENV PGHOST=postgres
ENV PGPORT=5433

ENV DD_APM_RECEIVER_SOCKET=/var/run/datadog/apm.socket
ENV UDS_WEBLOG=1

ENV DD_DATA_STREAMS_ENABLED=true

# docker startup
COPY utils/build/docker/nodejs/app.sh app.sh
RUN printf 'node app.js' >> app.sh
COPY utils/build/docker/set-uds-transport.sh set-uds-transport.sh
CMD ./app.sh

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh && rm -rf /root/.bun
ENV DD_TRACE_HEADER_TAGS=user-agent
