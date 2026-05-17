FROM node:20-alpine

COPY --from=oven/bun:1.3.13-alpine /usr/local/bin/bun /usr/local/bin/bun

RUN apk add --no-cache bash curl git jq

RUN node --version && npm --version && bun --version && curl --version

WORKDIR /usr/app

COPY utils/build/docker/nodejs/nextjs/package.json utils/build/docker/nodejs/nextjs/bun.lock ./
RUN bun install --frozen-lockfile --network-concurrency 8 --linker=hoisted

# docker build --progress=plain -f utils/build/docker/nodejs/nextjs.base.Dockerfile -t datadog/system-tests:nextjs.base-v1 .
# docker push datadog/system-tests:nextjs.base-v1
