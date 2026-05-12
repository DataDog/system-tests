FROM node:22-alpine

RUN apk add --no-cache bash curl git jq

RUN node --version && npm --version && curl --version

WORKDIR /usr/app

COPY utils/build/docker/nodejs/google_genai_app/package.json utils/build/docker/nodejs/google_genai_app/package-lock.json ./
RUN npm ci || (sleep 30 && npm ci)

# docker build --progress=plain -f utils/build/docker/nodejs/google_genai-js.base.Dockerfile -t datadog/system-tests:google_genai-js.base-v1 .
# docker push datadog/system-tests:google_genai-js.base-v1
