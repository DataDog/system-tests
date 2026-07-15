FROM node:22-alpine

COPY --from=oven/bun:1.3.13-alpine /usr/local/bin/bun /usr/local/bin/bun

RUN apk add --no-cache bash curl git jq

RUN node --version && npm --version && bun --version && curl --version

WORKDIR /usr/app

ENV NODE_ENV=production

COPY fastify/app.js ./
COPY fastify/dsm.js ./
COPY fastify/rasp.js ./
COPY fastify/debugger ./debugger
COPY fastify/iast ./iast
COPY fastify/integrations ./integrations
COPY fastify/resources ./resources
COPY fastify/package.json ./
COPY fastify/bun.lock ./
COPY nft-prune.mjs ./
RUN bun install --frozen-lockfile --network-concurrency 8 --linker=hoisted \
 && node nft-prune.mjs app.js \
 && rm -rf /root/.bun

# docker build --progress=plain -f utils/build/docker/nodejs/fastify.base.Dockerfile -t datadog/system-tests:fastify.base-v3 utils/build/docker/nodejs
# docker push datadog/system-tests:fastify.base-v3
