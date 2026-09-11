FROM datadog/system-tests:nextjs.base-v4

EXPOSE 7777

# Refresh the application route and dependencies baked into the base image.
COPY utils/build/docker/nodejs/nextjs/package.json utils/build/docker/nodejs/nextjs/bun.lock ./
COPY utils/build/docker/nodejs/nextjs/src/app/ffe ./src/app/ffe
RUN rm -rf node_modules \
 && bun install --frozen-lockfile --network-concurrency 8 --linker=hoisted

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh && rm -rf /root/.bun
RUN bun run build && rm -rf .next/cache
ENV DD_TRACE_HEADER_TAGS=user-agent

# docker startup
ENV DD_DATA_STREAMS_ENABLED=true
ENV PORT=7777
ENV HOSTNAME=0.0.0.0
COPY utils/build/docker/nodejs/app.sh app.sh
RUN printf './node_modules/.bin/next start' >> app.sh
ENV NODE_OPTIONS="--import dd-trace/initialize.mjs"
ENV DD_INJECT_FORCE=true
CMD ./app.sh
