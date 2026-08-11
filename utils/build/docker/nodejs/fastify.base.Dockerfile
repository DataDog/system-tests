FROM node:22-alpine

COPY --from=oven/bun:1.3.13-alpine /usr/local/bin/bun /usr/local/bin/bun

RUN apk add --no-cache bash curl git jq

RUN node --version && npm --version && bun --version && curl --version

WORKDIR /usr/app

ENV NODE_ENV=production

COPY utils/build/docker/nodejs/fastify/app.js \
     utils/build/docker/nodejs/fastify/dsm.js \
     utils/build/docker/nodejs/fastify/rasp.js \
     ./
COPY utils/build/docker/nodejs/fastify/debugger ./debugger
COPY utils/build/docker/nodejs/fastify/iast ./iast
COPY utils/build/docker/nodejs/fastify/integrations ./integrations
COPY utils/build/docker/nodejs/fastify/resources ./resources
COPY utils/build/docker/nodejs/fastify/package.json utils/build/docker/nodejs/fastify/bun.lock ./
COPY utils/build/docker/nodejs/nft-prune.mjs ./
RUN bun install --frozen-lockfile --network-concurrency 8 --linker=hoisted \
 && node nft-prune.mjs app.js \
 && rm -rf /root/.bun

# docker build --progress=plain -f utils/build/docker/nodejs/fastify.base.Dockerfile -t datadog/system-tests:fastify.base-v3 .
# docker push datadog/system-tests:fastify.base-v3
