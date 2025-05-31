FROM nginx:1.26.2

ARG NGINX_VERSION="1.26.2"
ENV NGINX_VERSION=${NGINX_VERSION}

RUN apt-get update \
 && apt-get install -y \
    wget tar jq curl xz-utils stress-ng binutils gcc libmicrohttpd-dev \
    procps gdb

RUN mkdir /builds /binaries

COPY utils/build/docker/cpp_nginx/nginx/nginx.conf /etc/nginx/nginx.conf.no-waf
COPY utils/build/docker/cpp_nginx/nginx/nginx-waf.conf /etc/nginx/nginx.conf.waf
COPY utils/build/docker/cpp_nginx/nginx/hello.html /builds/hello.html
COPY utils/build/docker/cpp_nginx/nginx/headers.txt /builds/headers.txt
COPY utils/build/docker/cpp_nginx/nginx/app.sh /builds/
COPY utils/build/docker/cpp_nginx/install_ddtrace.sh /builds/
COPY utils/build/docker/cpp_nginx/install_ddprof.sh /builds/
COPY utils/build/docker/cpp_nginx/ binaries* /builds/
COPY binaries/* /binaries/
COPY utils/build/docker/cpp_nginx/nginx/backend.c /tmp/

RUN gcc -O0 -g -o /usr/local/bin/backend /tmp/backend.c -lmicrohttpd && rm /tmp/backend.c

WORKDIR /builds

# NGINX Plugin setup
RUN ./install_ddtrace.sh

# Profiling setup
RUN ./install_ddprof.sh /usr/local/bin

# With or without the native profiler
ARG DDPROF_ENABLE="yes"
ENV DDPROF_ENABLE=${DDPROF_ENABLE}
CMD ["./app.sh"]
