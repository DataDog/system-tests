FROM ghcr.io/datadog/system-tests:parametric-nodejs.base-v6903

COPY utils/build/docker/nodejs/parametric/package.json /usr/app/
COPY utils/build/docker/nodejs/parametric/*.js /usr/app/
COPY utils/build/docker/nodejs/parametric/*.sh /usr/app/
COPY utils/build/docker/nodejs/parametric/npm/* /usr/app/

COPY utils/build/docker/nodejs/parametric/../install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
RUN mkdir /parametric-tracer-logs

CMD ["./app.sh"]
