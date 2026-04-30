FROM node:20-alpine

RUN apk add --no-cache bash curl git jq

RUN uname -r

# print versions
RUN node --version && npm --version && curl --version

WORKDIR /usr/app

COPY utils/build/docker/nodejs/nextjs /usr/app
RUN npm ci || (sleep 30 && npm ci)

EXPOSE 7777

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
RUN npm run build
ENV DD_TRACE_HEADER_TAGS=user-agent

# docker startup
ENV DD_DATA_STREAMS_ENABLED=true
# Let src/instrumentation.js handle Next.js shutdown signals manually, as documented in:
# https://nextjs.org/docs/pages/guides/self-hosting#manual-graceful-shutdowns
# Support was added in https://github.com/vercel/next.js/pull/59117; this
# weblog is pinned to Next.js >=14.0.4 to support NEXT_MANUAL_SIG_HANDLE.
ENV NEXT_MANUAL_SIG_HANDLE=true
ENV PORT=7777
ENV HOSTNAME=0.0.0.0
COPY utils/build/docker/nodejs/app.sh app.sh
ENV NODE_OPTIONS="--import dd-trace/initialize.mjs"
RUN printf 'exec ./node_modules/.bin/next start' >> app.sh
CMD ["./app.sh"]
