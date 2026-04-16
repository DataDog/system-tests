FROM maven:3-eclipse-temurin-21

WORKDIR /client
RUN mkdir ./tracer
COPY utils/build/docker/java/parametric/src src
COPY utils/build/docker/java/parametric/install_ddtrace.sh .
COPY utils/build/docker/java/parametric/pom.xml .
COPY binaries /binaries
RUN bash install_ddtrace.sh
COPY utils/build/docker/java/parametric/run.sh .
RUN mkdir /parametric-tracer-logs

# Build locale_init.so: sets LC_ALL from TEST_LOCALE at process startup via LD_PRELOAD
RUN apt-get update && apt-get install -y --no-install-recommends locales gcc \
    && echo "de_DE.UTF-8 UTF-8" >> /etc/locale.gen && locale-gen \
    && printf '#include <locale.h>\n#include <stdlib.h>\n__attribute__((constructor)) static void init_locale(void){const char*l=getenv("TEST_LOCALE");if(l&&*l)setlocale(LC_ALL,l);}' > /tmp/li.c \
    && gcc -shared -fPIC -o /locale_init.so /tmp/li.c \
    && rm /tmp/li.c && rm -rf /var/lib/apt/lists/*

CMD ["./run.sh"]
