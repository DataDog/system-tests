FROM nginx:1.25.4

ARG NGINX_VERSION="1.25.4"
ENV NGINX_VERSION=${NGINX_VERSION}

RUN apt-get update \
 && apt-get install -y wget tar jq curl xz-utils stress-ng

RUN mkdir /app

COPY utils/build/docker/cpp/nginx/nginx.conf /etc/nginx/nginx.conf
COPY utils/build/docker/cpp/nginx/hello.html /app/hello.html
COPY utils/build/docker/cpp/nginx/install_ddtrace.sh /app/
COPY utils/build/docker/cpp/install_ddprof.sh /app/
COPY utils/build/docker/cpp/nginx/app.sh /app/
COPY utils/build/docker/cpp/ binaries* /app/

WORKDIR /app

# NGINX Plugin setup 
RUN ./install_ddtrace.sh

# Profiling setup
RUN ./install_ddprof.sh /usr/local/bin

# With or without the native profiler
ARG DDPROF_ENABLE="yes"
ENV DDPROF_ENABLE=${DDPROF_ENABLE}
CMD ["./app.sh"]
