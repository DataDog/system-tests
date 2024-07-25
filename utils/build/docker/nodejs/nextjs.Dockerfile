FROM datadog/system-tests:nextjs.base-v0

RUN uname -r
RUN node --version && npm --version && curl --version

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
COPY utils/build/docker/nodejs/app.sh \
     utils/build/docker/nodejs/nextjs \
     /usr/app/

RUN npm install
RUN chmod +x /binaries/install_ddtrace.sh app.sh
RUN /binaries/install_ddtrace.sh
RUN npm run build
RUN printf '#!/bin/bash\nnode .next/standalone/server.js' > app.sh

ENV NODE_OPTIONS="--require dd-trace/init.js"