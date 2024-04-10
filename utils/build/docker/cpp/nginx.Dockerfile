FROM nginx:1.25.4

ARG NGINX_VERSION="1.25.4"
ENV NGINX_VERSION=${NGINX_VERSION}

RUN mkdir /builds

# Copy needs a single valid source (ddprof tar can be missing)
COPY utils/build/docker/cpp/nginx/nginx.conf /etc/nginx/nginx.conf
COPY utils/build/docker/cpp/nginx/hello.html /builds/hello.html
COPY utils/build/docker/cpp/nginx/install_ddtrace.sh /builds/
COPY utils/build/docker/cpp/install_ddprof.sh binaries* /builds/

RUN apt-get update \
 && apt-get install -y wget tar jq curl xz-utils stress-ng

# NGINX Plugin setup 
RUN /builds/install_ddtrace.sh

# Profiling setup
RUN cd /builds && ./install_ddprof.sh /usr/local/bin

COPY utils/build/docker/cpp/nginx/app.sh ./

# With or without the native profiler
ARG DDPROF_ENABLE="yes"
ENV DDPROF_ENABLE=${DDPROF_ENABLE}
CMD ["./app.sh"]
