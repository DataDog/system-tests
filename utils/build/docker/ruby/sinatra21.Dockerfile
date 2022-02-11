FROM ghcr.io/datadog/system-tests-apps-ruby/sinatra21:latest

COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

CMD ["./app.sh", "PUMA"]
