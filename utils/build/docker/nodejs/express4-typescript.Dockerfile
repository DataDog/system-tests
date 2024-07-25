FROM datadog/system-tests:express4.base-v0

RUN uname -r
RUN node --version && npm --version && curl --version

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
COPY utils/build/docker/nodejs/app.sh \
     utils/build/docker/nodejs/express4-typescript \
     /usr/app/

RUN npm install
RUN printf '#!/bin/bash\nnode dist/app.js' > app.sh
RUN chmod +x /binaries/install_ddtrace.sh app.sh
RUN /binaries/install_ddtrace.sh
RUN npm run build
