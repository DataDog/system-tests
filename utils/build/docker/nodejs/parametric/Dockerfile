
FROM node:18.10-slim
RUN apt-get update && apt-get -y install bash curl git jq \
  || sleep 60 && apt-get update && apt-get -y install bash curl git jq
COPY --from=oven/bun:1.3.13 /usr/local/bin/bun /usr/local/bin/bun
WORKDIR /usr/app
COPY utils/build/docker/nodejs/parametric/package.json /usr/app/
COPY utils/build/docker/nodejs/parametric/bun.lock /usr/app/
COPY utils/build/docker/nodejs/parametric/*.js /usr/app/
COPY utils/build/docker/nodejs/parametric/*.sh /usr/app/
COPY utils/build/docker/nodejs/parametric/npm/* /usr/app/

RUN bun install --frozen-lockfile --linker=hoisted --network-concurrency 8

COPY utils/build/docker/nodejs/parametric/../install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
RUN mkdir /parametric-tracer-logs

CMD ["./app.sh"]

