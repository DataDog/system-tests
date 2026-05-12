FROM node:22-alpine

RUN apk add --no-cache bash curl git jq

RUN node --version && npm --version && curl --version

WORKDIR /usr/app

ENV NODE_ENV=production

COPY utils/build/docker/nodejs/fastify/package.json utils/build/docker/nodejs/fastify/package-lock.json ./
RUN npm ci || (sleep 30 && npm ci)

# docker build --progress=plain -f utils/build/docker/nodejs/fastify.base.Dockerfile -t datadog/system-tests:fastify.base-v1 .
# docker push datadog/system-tests:fastify.base-v1
