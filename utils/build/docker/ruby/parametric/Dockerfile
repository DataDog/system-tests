FROM --platform=linux/amd64 ruby:3.2.1-bullseye

WORKDIR /app
COPY utils/build/docker/ruby/parametric .
COPY utils/build/docker/ruby/parametric/../install_ddtrace.sh binaries* /binaries/
COPY utils/build/docker/ruby/parametric/system_tests_library_version.sh system_tests_library_version.sh
RUN bundle install
RUN /binaries/install_ddtrace.sh
COPY utils/build/docker/ruby/parametric/server.rb /app/
RUN mkdir /parametric-tracer-logs

CMD ["bundle", "exec", "ruby", "server.rb"]