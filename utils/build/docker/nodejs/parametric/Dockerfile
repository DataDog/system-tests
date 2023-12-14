
FROM node:18.10-slim
RUN apt-get update && apt-get install -y jq git
WORKDIR /usr/app
COPY utils/build/docker/nodejs/parametric/package.json /usr/app/
COPY utils/build/docker/nodejs/parametric/package-lock.json /usr/app/
COPY utils/build/docker/nodejs/parametric/*.js /usr/app/
COPY utils/build/docker/nodejs/parametric/npm/* /usr/app/

RUN npm install

COPY utils/build/docker/nodejs/parametric/../install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

