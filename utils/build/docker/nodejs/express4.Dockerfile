FROM datadog/system-tests:express4.base-v0

RUN uname -r
RUN node --version && npm --version && curl --version

COPY utils/build/docker/nodejs/express4 /usr/app

ENV NODE_ENV=production

RUN npm install
RUN printf '#!/bin/bash\nnode app.js' > app.sh
RUN /binaries/install_ddtrace.sh

# docker build -f utils/build/docker/express4.Dockerfile -t test .
# docker run -ti -p 7777:7777 test
