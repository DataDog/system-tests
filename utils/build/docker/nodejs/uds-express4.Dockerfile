FROM datadog/system-tests:express4.base-v0

RUN uname -r
RUN node --version && npm --version && curl --version

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
COPY utils/build/docker/nodejs/app.sh \
     utils/build/docker/set-uds-transport.sh \
     utils/build/docker/nodejs/express4 \
     /usr/app/

ENV DD_APM_RECEIVER_SOCKET=/var/run/datadog/apm.socket
ENV UDS_WEBLOG=1

RUN npm install
RUN chmod +x /binaries/install_ddtrace.sh app.sh
RUN /binaries/install_ddtrace.sh
