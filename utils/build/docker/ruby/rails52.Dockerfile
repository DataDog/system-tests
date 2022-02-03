FROM ghcr.io/datadog/system-tests-apps-ruby/rails52:latest

COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

ENV DD_TRACE_SAMPLE_RATE=0.5
ENV DD_TAGS='key1:val1, key2 : val2 '

CMD bundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1
