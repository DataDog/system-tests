FROM node:18.10-slim

RUN apt-get update && apt-get -y install bash curl git jq \
  || sleep 60 && apt-get update && apt-get -y install bash curl git jq

RUN node --version && npm --version && curl --version

WORKDIR /usr/app

COPY utils/build/docker/nodejs/parametric/package.json utils/build/docker/nodejs/parametric/package-lock.json ./
RUN npm install || sleep 60 && npm install

# docker build --progress=plain -f utils/build/docker/nodejs/parametric.base.Dockerfile -t datadog/system-tests:parametric-nodejs.base-v1 .
# docker push datadog/system-tests:parametric-nodejs.base-v1
