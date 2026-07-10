FROM datadog/system-tests:express4.base-v3

# The base image bakes in app.js; refresh it (and fork_child.js, which is loaded via a
# runtime path so it is never bundled) so the /spawn_child endpoint is present.
COPY utils/build/docker/nodejs/express/app.js app.js
COPY utils/build/docker/nodejs/express/fork_child.js fork_child.js

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

# docker build -f utils/build/docker/nodejs/express4.Dockerfile -t test .
# docker run -ti -p 7777:7777 test
