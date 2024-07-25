FROM datadog/system-tests:nextjs.base-v0

RUN uname -r
RUN node --version && npm --version && curl --version

COPY utils/build/docker/nodejs/nextjs /usr/app

RUN npm install
RUN /binaries/install_ddtrace.sh
RUN npm run build

RUN printf '#!/bin/bash\nnode .next/standalone/server.js' > app.sh
ENV NODE_OPTIONS="--require dd-trace/init.js"
