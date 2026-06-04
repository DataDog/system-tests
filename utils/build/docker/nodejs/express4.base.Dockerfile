FROM node:18-alpine

COPY --from=oven/bun:1.3.13-alpine /usr/local/bin/bun /usr/local/bin/bun

RUN apk add --no-cache bash curl git jq

RUN node --version && npm --version && bun --version && curl --version

WORKDIR /usr/app

ENV NODE_ENV=production

COPY utils/build/docker/nodejs/express /usr/app
COPY utils/build/docker/nodejs/express4/package.json utils/build/docker/nodejs/express4/bun.lock ./
COPY utils/build/docker/nodejs/nft-prune.mjs ./
RUN bun install --frozen-lockfile --network-concurrency 8 --linker=hoisted \
 && node nft-prune.mjs app.js \
 && find node_modules -type d -empty -delete \
 && rm -rf /root/.bun nft-prune.mjs

# docker build --progress=plain -f utils/build/docker/nodejs/express4.base.Dockerfile -t datadog/system-tests:express4.base-v2 .
# docker push datadog/system-tests:express4.base-v2
