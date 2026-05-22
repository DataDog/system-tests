FROM node:18-alpine

COPY --from=oven/bun:1.3.13-alpine /usr/local/bin/bun /usr/local/bin/bun

RUN apk add --no-cache bash curl git jq

RUN node --version && npm --version && bun --version && curl --version

WORKDIR /usr/app

ENV NODE_ENV=production

COPY utils/build/docker/nodejs/express4/package.json utils/build/docker/nodejs/express4/bun.lock ./
RUN bun install --frozen-lockfile --network-concurrency 8 --linker=hoisted

# docker build --progress=plain -f utils/build/docker/nodejs/express4.base.Dockerfile -t datadog/system-tests:express4.base-v1 .
# docker push datadog/system-tests:express4.base-v1
