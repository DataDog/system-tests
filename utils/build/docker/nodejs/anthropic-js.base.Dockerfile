FROM node:22-alpine

RUN apk add --no-cache bash curl git jq

RUN node --version && npm --version && curl --version

WORKDIR /usr/app

COPY utils/build/docker/nodejs/anthropic_app/package.json utils/build/docker/nodejs/anthropic_app/package-lock.json ./
RUN npm ci || (sleep 30 && npm ci)

# docker build --progress=plain -f utils/build/docker/nodejs/anthropic-js.base.Dockerfile -t datadog/system-tests:anthropic-js.base-v1 .
# docker push datadog/system-tests:anthropic-js.base-v1
