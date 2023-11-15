FROM ruby:3.2.1-bullseye

ARG BUILD_MODULE=''

WORKDIR /client
RUN gem install ddtrace # Install a baseline ddtrace version, to cache all dependencies
COPY ./utils/build/docker/ruby/parametric/Gemfile /client/
COPY ./utils/build/docker/ruby/parametric/install_dependencies.sh /client/
ENV RUBY_DDTRACE_SHA=$BUILD_MODULE
RUN bash install_dependencies.sh
CMD bundle exec ruby -e 'puts Gem.loaded_specs["ddtrace"].version'
