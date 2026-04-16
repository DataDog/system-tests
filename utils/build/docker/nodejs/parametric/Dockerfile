
FROM node:18.10-slim
RUN apt-get update && apt-get -y install bash curl git jq locales gcc libc6-dev \
  || sleep 60 && apt-get update && apt-get -y install bash curl git jq locales gcc libc6-dev
WORKDIR /usr/app
COPY utils/build/docker/nodejs/parametric/package.json /usr/app/
COPY utils/build/docker/nodejs/parametric/package-lock.json /usr/app/
COPY utils/build/docker/nodejs/parametric/*.js /usr/app/
COPY utils/build/docker/nodejs/parametric/*.sh /usr/app/
COPY utils/build/docker/nodejs/parametric/npm/* /usr/app/

RUN npm install || sleep 60 && npm install

COPY utils/build/docker/nodejs/parametric/../install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh
RUN mkdir /parametric-tracer-logs

# Build locale_init.so: sets LC_ALL from TEST_LOCALE at process startup via LD_PRELOAD
RUN echo "de_DE.UTF-8 UTF-8" >> /etc/locale.gen && locale-gen \
    && printf '#include <locale.h>\n#include <stdlib.h>\n__attribute__((constructor)) static void init_locale(void){const char*l=getenv("TEST_LOCALE");if(l&&*l)setlocale(LC_ALL,l);}' > /tmp/li.c \
    && gcc -shared -fPIC -o /locale_init.so /tmp/li.c \
    && rm /tmp/li.c && rm -rf /var/lib/apt/lists/*

CMD ["./app.sh"]

