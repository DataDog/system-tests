FROM node:20-alpine

COPY --from=oven/bun:1.3.13-alpine /usr/local/bin/bun /usr/local/bin/bun

RUN apk add --no-cache bash curl git jq

RUN node --version && npm --version && bun --version && curl --version

WORKDIR /usr/app

COPY utils/build/docker/nodejs/nextjs/package.json utils/build/docker/nodejs/nextjs/bun.lock ./
COPY utils/build/docker/nodejs/nextjs /usr/app
COPY utils/build/docker/nodejs/nft-prune.mjs ./
RUN bun install --frozen-lockfile --network-concurrency 8 --linker=hoisted \
 && bun run build \
 && node nft-prune.mjs \
      --keep-dir=node_modules/next/dist/compiled \
      node_modules/next/dist/bin/next \
 && rm -rf \
      node_modules/next/dist/compiled/*experimental \
      node_modules/next/dist/compiled/react-server-dom-turbopack \
      node_modules/next/dist/compiled/babel \
      node_modules/next/dist/compiled/babel-packages \
      node_modules/next/dist/compiled/terser \
 && rm -rf .next/cache /root/.bun

# docker build --progress=plain -f utils/build/docker/nodejs/nextjs.base.Dockerfile -t datadog/system-tests:nextjs.base-v3 .
# docker push datadog/system-tests:nextjs.base-v3
