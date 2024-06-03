FROM nginx:1.25.4

ARG NGINX_VERSION="1.25.4"
ENV NGINX_VERSION=${NGINX_VERSION}

RUN apt-get update \
 && apt-get install -y wget tar jq curl xz-utils stress-ng binutils gcc libmicrohttpd-dev

RUN mkdir /builds

COPY utils/build/docker/cpp/nginx/nginx.conf /etc/nginx/nginx.conf.no-waf
COPY utils/build/docker/cpp/nginx/nginx-waf.conf /etc/nginx/nginx.conf.waf
COPY utils/build/docker/cpp/nginx/hello.html /builds/hello.html
COPY utils/build/docker/cpp/nginx/install_ddtrace.sh /builds/
COPY utils/build/docker/cpp/install_ddprof.sh /builds/
COPY utils/build/docker/cpp/nginx/app.sh /builds/
COPY utils/build/docker/cpp/ binaries* /builds/
COPY utils/build/docker/cpp/nginx/backend.c /tmp/

# install backend app
RUN gcc -o /usr/local/bin/backend /tmp/backend.c -lmicrohttpd && rm /tmp/backend.c

WORKDIR /builds

# NGINX Plugin setup
RUN ./install_ddtrace.sh

# Profiling setup
RUN ./install_ddprof.sh /usr/local/bin

# With or without the native profiler
ARG DDPROF_ENABLE="yes"
ENV DDPROF_ENABLE=${DDPROF_ENABLE}
CMD ["./app.sh"]
