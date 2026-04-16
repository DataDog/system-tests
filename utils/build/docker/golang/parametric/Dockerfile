
FROM golang:1.25

# install jq, locales, and gcc for locale_init.so
RUN apt-get update && apt-get -y install jq locales gcc
ENV GONOSUMDB=github.com/DataDog/* \
    GOPRIVATE=github.com/DataDog/*
WORKDIR /app
COPY utils/build/docker/golang/parametric/go.mod /app
COPY utils/build/docker/golang/parametric/go.sum /app
COPY utils/build/docker/golang/parametric/. /app
# download the proper tracer version
COPY utils/build/docker/golang/install_ddtrace.sh binaries* /binaries/
COPY utils/build/docker/golang/parametric/system_tests_library_version.sh system_tests_library_version.sh
RUN /binaries/install_ddtrace.sh
RUN mkdir /parametric-tracer-logs

RUN go install

# Build locale_init.so: sets LC_ALL from TEST_LOCALE at process startup via LD_PRELOAD
RUN echo "de_DE.UTF-8 UTF-8" >> /etc/locale.gen && locale-gen \
    && printf '#include <locale.h>\n#include <stdlib.h>\n__attribute__((constructor)) static void init_locale(void){const char*l=getenv("TEST_LOCALE");if(l&&*l)setlocale(LC_ALL,l);}' > /tmp/li.c \
    && gcc -shared -fPIC -o /locale_init.so /tmp/li.c \
    && rm /tmp/li.c && rm -rf /var/lib/apt/lists/*

CMD ["bash", "-c", "[ -n \"${TEST_LOCALE:-}\" ] && export LD_PRELOAD=/locale_init.so; exec main"]
