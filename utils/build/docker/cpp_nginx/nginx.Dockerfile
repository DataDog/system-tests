FROM debian:bookworm-slim

ARG NGINX_VERSION="1.28.0"
ENV NGINX_VERSION=${NGINX_VERSION}

RUN groupadd --system --gid 101 nginx \
    && useradd --system --gid nginx -M --home /nonexistent --comment "nginx user" --shell /bin/false --uid 101 nginx

# Install build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        libpcre3-dev \
        libssl-dev \
        zlib1g-dev \
        libgeoip-dev \
        libmaxminddb-dev \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/nginx-src \
    && cd /opt/nginx-src \
    && curl -fsSL https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz -o nginx.tar.gz \
    && tar -xzf nginx.tar.gz \
    && rm nginx.tar.gz

RUN git clone --depth 1 https://github.com/leev/ngx_http_geoip2_module.git /opt/nginx-src/ngx_http_geoip2_module

WORKDIR /tmp/nginx-${NGINX_VERSION}
RUN cd /opt/nginx-src/nginx-${NGINX_VERSION} && ./configure \
        --user=nginx \
        --with-cc-opt='-g -O0 -fPIC -Wdate-time -D_FORTIFY_SOURCE=2' \
        --with-ld-opt='-Wl,-Bsymbolic-functions -Wl,-z,relro -Wl,-z,now -fPIC' \
        --prefix=/usr/lib/nginx \
        --sbin-path=/usr/sbin \
        --conf-path=/etc/nginx/nginx.conf \
        --http-log-path=/var/log/nginx/access.log \
        --error-log-path=/var/log/nginx/error.log \
        --lock-path=/var/lock/nginx.lock \
        --pid-path=/run/nginx.pid \
        --modules-path=/usr/lib/nginx/modules \
        --http-client-body-temp-path=/var/lib/nginx/body \
        --http-fastcgi-temp-path=/var/lib/nginx/fastcgi \
        --http-proxy-temp-path=/var/lib/nginx/proxy \
        --http-scgi-temp-path=/var/lib/nginx/scgi \
        --http-uwsgi-temp-path=/var/lib/nginx/uwsgi \
        --with-compat \
        --with-debug \
        --with-pcre-jit \
        --with-http_ssl_module \
        --with-http_stub_status_module \
        --with-http_realip_module \
        --with-http_auth_request_module \
        --with-http_v2_module \
        --with-http_v3_module \
        --with-http_dav_module \
        --with-http_slice_module \
        --with-threads \
        --add-dynamic-module=/opt/nginx-src/ngx_http_geoip2_module \
        --with-http_addition_module \
        --with-http_gunzip_module \
        --with-http_gzip_static_module \
        --with-http_sub_module \
    && make -j$(nproc) \
    && make install

RUN mkdir -p /var/lib/nginx/{body,fastcgi,proxy,scgi,uwsgi} \
    && chown -R nginx:nginx /var/lib/nginx

EXPOSE 80

STOPSIGNAL SIGQUIT

RUN apt-get update && \
    apt-get install -y \
      wget tar jq curl xz-utils stress-ng binutils gcc libmicrohttpd-dev \
      procps gdb \
    && rm -rf /var/lib/apt/lists/*

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
COPY utils/build/docker/cpp_nginx/nginx/nginx_gdb.py /root/

RUN echo "source /root/nginx_gdb.py" >> /root/.gdbinit

RUN gcc -O0 -g -o /usr/local/bin/backend /tmp/backend.c -lmicrohttpd && rm /tmp/backend.c

WORKDIR /builds

# NGINX Plugin setup
RUN ./install_ddtrace.sh

# Profiling setup
RUN ./install_ddprof.sh /usr/local/bin

CMD ["./app.sh"]
