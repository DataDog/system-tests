FROM ruby:3.2.1-bullseye

WORKDIR /app
COPY utils/build/docker/ruby/parametric/ .
COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN bundle install
RUN /binaries/install_ddtrace.sh
CMD cat SYSTEM_TESTS_LIBRARY_VERSION
