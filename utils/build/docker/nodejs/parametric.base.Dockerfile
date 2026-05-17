FROM node:18.10-slim

COPY --from=oven/bun:1.3.13 /usr/local/bin/bun /usr/local/bin/bun

RUN apt-get update && apt-get -y install bash curl git jq \
  || sleep 60 && apt-get update && apt-get -y install bash curl git jq

RUN node --version && npm --version && bun --version && curl --version

WORKDIR /usr/app

COPY utils/build/docker/nodejs/parametric/package.json utils/build/docker/nodejs/parametric/bun.lock ./
RUN bun install --frozen-lockfile --network-concurrency 8 --linker=hoisted

# docker build --progress=plain -f utils/build/docker/nodejs/parametric.base.Dockerfile -t datadog/system-tests:parametric-nodejs.base-v1 .
# docker push datadog/system-tests:parametric-nodejs.base-v1
