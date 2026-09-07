FROM node:18.10-slim

COPY --from=oven/bun:1.3.13 /usr/local/bin/bun /usr/local/bin/bun

# Debian 11 LTS ended 2026-08-31; live security repos 404 — use archive only
# node:18.10-slim is Bullseye
RUN set -ex && \
  sed -i 's|deb.debian.org|archive.debian.org|g' /etc/apt/sources.list && \
  sed -i -E '/security\.debian\.org|debian-security|bullseye-security/d' /etc/apt/sources.list && \
  echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99no-check-valid-until && \
  apt-get update && apt-get -y install bash curl git jq

RUN node --version && npm --version && bun --version && curl --version

WORKDIR /usr/app
COPY utils/build/docker/nodejs/parametric/package.json utils/build/docker/nodejs/parametric/bun.lock /usr/app/
COPY utils/build/docker/nodejs/parametric/*.js /usr/app/
COPY utils/build/docker/nodejs/parametric/*.sh /usr/app/
COPY utils/build/docker/nodejs/parametric/npm/* /usr/app/

RUN bun install --frozen-lockfile --network-concurrency 8 --linker=hoisted

COPY utils/build/docker/nodejs/parametric/../install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
RUN mkdir /parametric-tracer-logs

CMD ["./app.sh"]
