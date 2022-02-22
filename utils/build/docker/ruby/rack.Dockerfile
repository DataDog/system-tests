FROM ghcr.io/datadog/system-tests-apps-ruby/rack:latest

COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

CMD bundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1
