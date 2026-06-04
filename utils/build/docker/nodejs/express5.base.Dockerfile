FROM node:18-alpine

COPY --from=oven/bun:1.3.13-alpine /usr/local/bin/bun /usr/local/bin/bun

RUN apk add --no-cache bash curl git jq

RUN node --version && npm --version && bun --version && curl --version

WORKDIR /usr/app

ENV NODE_ENV=production

COPY utils/build/docker/nodejs/express /usr/app
COPY utils/build/docker/nodejs/express5/package.json utils/build/docker/nodejs/express5/bun.lock ./
COPY utils/build/docker/nodejs/nft-prune.mjs ./
RUN bun install --frozen-lockfile --network-concurrency 8 --linker=hoisted \
 && node nft-prune.mjs app.js \
 && rm -rf /root/.bun

# docker build --progress=plain -f utils/build/docker/nodejs/express5.base.Dockerfile -t datadog/system-tests:express5.base-v2 .
# docker push datadog/system-tests:express5.base-v2
