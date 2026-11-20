ARG BASE_IMAGE
FROM ${BASE_IMAGE}
WORKDIR /app

ENV RAILS_ENV=production \
    SECRET_KEY_BASE=1234567890abcdef \
    RAILS_LOG_TO_STDOUT=1 \
    RAILS_SERVE_STATIC_FILES=1 \
    PATH=/usr/local/rvm/wrappers/default:$PATH

COPY lib-injection/build/docker/ruby/lib_injection_rails_app/ .
RUN set -eu; \
    rm -f .ruby-version; \
    ruby -e 'abort "expected RVM Ruby" unless File.realpath(RbConfig.ruby).start_with?("/usr/local/rvm/rubies/")'; \
    ruby_minor="$(ruby -e 'print RUBY_VERSION.split(".").take(2).join(".")')"; \
    cp "gemfiles/ruby-${ruby_minor}.gemfile.lock" Gemfile.lock; \
    env DD_APM_INSTRUMENTATION_DEBUG=false bundle install

EXPOSE 18080
CMD ["bundle", "exec", "rails", "server", "-b", "0.0.0.0", "-p", "18080"]
