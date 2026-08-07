FROM node:18-alpine

COPY --from=oven/bun:1.3.13-alpine /usr/local/bin/bun /usr/local/bin/bun

RUN apk add --no-cache bash curl git jq

RUN node --version && npm --version && bun --version && curl --version

WORKDIR /usr/app

COPY express4-typescript /usr/app
COPY express4-typescript/package.json ./
COPY express4-typescript/bun.lock ./
COPY nft-prune.mjs ./
RUN bun install --frozen-lockfile --network-concurrency 8 --linker=hoisted \
 && node nft-prune.mjs --keep-types app.ts node_modules/typescript/bin/tsc \
 && rm -rf /root/.bun

# docker build --progress=plain -f utils/build/docker/nodejs/express4-typescript.base.Dockerfile -t datadog/system-tests:express4-typescript.base-v3 utils/build/docker/nodejs
# docker push datadog/system-tests:express4-typescript.base-v3
