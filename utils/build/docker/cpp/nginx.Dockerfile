# FROM nginx:1.17.3
FROM nginx:1.25.2

RUN apt-get update && \
  apt-get install -y wget tar jq curl xz-utils \
    stress-ng

ADD utils/build/docker/cpp/nginx/nginx.conf /etc/nginx/nginx.conf

RUN echo '{}' > /etc/nginx/dd-config.json

RUN mkdir /builds

# Copy needs a single valid source (ddprof tar can be missing)
COPY utils/build/docker/cpp/install_ddprof.sh binaries* /builds/
COPY utils/build/docker/cpp/nginx/install_ddtrace.sh /builds/
RUN /builds/install_ddtrace.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'

# Profiling setup

RUN cd /builds && ./install_ddprof.sh /usr/local/bin

COPY utils/build/docker/cpp/nginx/app.sh ./

# With or without the native profiler
ARG DDPROF_ENABLE="yes"
ENV DDPROF_ENABLE=${DDPROF_ENABLE}
CMD ["./app.sh"]
