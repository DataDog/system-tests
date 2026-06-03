FROM node:20-alpine

COPY --from=oven/bun:1.3.13-alpine /usr/local/bin/bun /usr/local/bin/bun

RUN apk add --no-cache bash curl git jq

RUN node --version && npm --version && bun --version && curl --version

COPY --chmod=755 utils/build/docker/nodejs/cleanup-node-modules.sh \
    /usr/local/bin/cleanup-node-modules

WORKDIR /usr/app

COPY utils/build/docker/nodejs/nextjs/package.json utils/build/docker/nodejs/nextjs/bun.lock ./
RUN bun install --frozen-lockfile --network-concurrency 8 --linker=hoisted \
 && cleanup-node-modules

COPY utils/build/docker/nodejs/nextjs /usr/app
RUN bun run build \
 && rm -rf .next/cache src README.md bun.lock package-lock.json jsconfig.json

# docker build --progress=plain -f utils/build/docker/nodejs/nextjs.base.Dockerfile -t datadog/system-tests:nextjs.base-v2 .
# docker push datadog/system-tests:nextjs.base-v2
