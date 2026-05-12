FROM node:18-alpine

RUN apk add --no-cache bash curl git jq

RUN node --version && npm --version && curl --version

WORKDIR /usr/app

COPY utils/build/docker/nodejs/express4-typescript/package.json utils/build/docker/nodejs/express4-typescript/package-lock.json ./
RUN npm ci || (sleep 30 && npm ci)

# docker build --progress=plain -f utils/build/docker/nodejs/express4-typescript.base.Dockerfile -t datadog/system-tests:express4-typescript.base-v1 .
# docker push datadog/system-tests:express4-typescript.base-v1
