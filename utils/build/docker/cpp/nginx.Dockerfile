FROM nginx:1.25.4

RUN apt-get update && \
  apt-get install -y wget tar jq curl xz-utils \
    stress-ng

RUN echo '\n\
env DD_AGENT_HOST;\n\
env DD_SERVICE;\n\
env DD_TRACE_SAMPLE_RATE;\n\
env DD_TRACE_DEBUG;\n\
load_module modules/ngx_http_opentracing_module.so;\n\
events {\n\
    worker_connections  1024;\n\
}\n\
http {\n\
    opentracing_load_tracer /usr/local/lib/libdd_opentracing_plugin.so /etc/nginx/dd-config.json;\n\
    opentracing on;\n\
    opentracing_tag http_user_agent \$http_user_agent;\n\
    opentracing_trace_locations off;\n\
    opentracing_operation_name "\$request_method \$uri";\n\
    log_format with_trace_id '\''\$remote_addr - \$http_x_forwarded_user [\$time_local] "\$request" '\''\n\
        '\''\$status \$body_bytes_sent "\$http_referer" '\''\n\
        '\''"\$http_user_agent" "\$http_x_forwarded_for" '\''\n\
        '\''"\$opentracing_context_x_datadog_trace_id" "\$opentracing_context_x_datadog_parent_id"'\'';\n\
    access_log /var/log/nginx/access.log with_trace_id;\n\
    server {\n\
        listen       7777;\n\
        server_name  0.0.0.0;\n\
        location ~* /sample_rate/([0-9]+) { return 200  '\''OK'\''; }\n\
        location / { return 200 '\''Hello world\n'\''; }\n\
    }\n\
}' > /etc/nginx/nginx.conf

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
