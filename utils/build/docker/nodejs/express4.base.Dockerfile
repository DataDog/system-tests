FROM node:18-alpine

RUN apk add --no-cache bash curl git jq

RUN node --version && npm --version && curl --version

WORKDIR /usr/app

ENV NODE_ENV=production

COPY utils/build/docker/nodejs/express4/package.json utils/build/docker/nodejs/express4/package-lock.json ./
RUN npm ci || (sleep 30 && npm ci)

# docker build --progress=plain -f utils/build/docker/nodejs/express4.base.Dockerfile -t datadog/system-tests:express4.base-v1 .
# docker push datadog/system-tests:express4.base-v1
