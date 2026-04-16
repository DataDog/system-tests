
# Build locale_init.so and generate de_DE locale in a matching Ubuntu stage.
# maven:eclipse-temurin is Ubuntu Jammy-based; using the same base ensures the
# compiled .so and locale-archive are binary-compatible with the target image.
# Doing this in a separate stage avoids a 600s Docker build timeout caused by
# apt-get being slow on the large maven image.
FROM ubuntu:22.04 AS locale-tools
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev locales \
    && echo "de_DE.UTF-8 UTF-8" >> /etc/locale.gen && locale-gen \
    && printf '#include <locale.h>\n#include <stdlib.h>\n__attribute__((constructor)) static void init_locale(void){const char*l=getenv("TEST_LOCALE");if(l&&*l)setlocale(LC_ALL,l);}' > /tmp/li.c \
    && gcc -shared -fPIC -o /locale_init.so /tmp/li.c

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

# Copy locale_init.so and locale archive from the Ubuntu builder
COPY --from=locale-tools /locale_init.so /locale_init.so
COPY --from=locale-tools /usr/lib/locale/locale-archive /usr/lib/locale/locale-archive

CMD ["./run.sh"]
