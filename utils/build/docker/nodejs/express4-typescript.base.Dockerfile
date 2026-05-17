FROM node:18-alpine

COPY --from=oven/bun:1.3.13-alpine /usr/local/bin/bun /usr/local/bin/bun

RUN apk add --no-cache bash curl git jq

RUN node --version && npm --version && bun --version && curl --version

WORKDIR /usr/app

COPY utils/build/docker/nodejs/express4-typescript/package.json utils/build/docker/nodejs/express4-typescript/bun.lock ./
RUN bun install --frozen-lockfile --network-concurrency 8 --linker=hoisted

# docker build --progress=plain -f utils/build/docker/nodejs/express4-typescript.base.Dockerfile -t datadog/system-tests:express4-typescript.base-v1 .
# docker push datadog/system-tests:express4-typescript.base-v1
