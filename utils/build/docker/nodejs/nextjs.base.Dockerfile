FROM node:20-alpine

RUN apk add --no-cache bash curl git jq

RUN node --version && npm --version && curl --version

WORKDIR /usr/app

COPY utils/build/docker/nodejs/nextjs/package.json utils/build/docker/nodejs/nextjs/package-lock.json ./
RUN npm ci || (sleep 30 && npm ci)

# docker build --progress=plain -f utils/build/docker/nodejs/nextjs.base.Dockerfile -t datadog/system-tests:nextjs.base-v1 .
# docker push datadog/system-tests:nextjs.base-v1
