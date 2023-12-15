FROM ruby:3.2.1-bullseye

#RUN curl -O https://rubygems.org/downloads/libv8-node-15.14.0.1-$(arch)-linux.gem && gem install libv8-node-15.14.0.1-$(arch)-linux.gem && rm libv8-node-15.14.0.1-$(arch)-linux.gem

WORKDIR /app
COPY utils/build/docker/ruby/parametric/ .
COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN bundle install
RUN /binaries/install_ddtrace.sh
CMD cat SYSTEM_TESTS_LIBRARY_VERSION
