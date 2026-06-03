FROM datadog/system-tests:nextjs.base-v2

EXPOSE 7777

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
ENV DD_TRACE_HEADER_TAGS=user-agent

# docker startup
ENV DD_DATA_STREAMS_ENABLED=true
ENV PORT=7777
ENV HOSTNAME=0.0.0.0
COPY utils/build/docker/nodejs/app.sh app.sh
RUN printf './node_modules/.bin/next start' >> app.sh
ENV NODE_OPTIONS="--import dd-trace/initialize.mjs"
CMD ./app.sh
