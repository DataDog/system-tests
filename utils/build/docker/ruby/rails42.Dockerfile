FROM ghcr.io/datadog/images-rb/engines/ruby:2.5

RUN curl -O https://rubygems.org/downloads/libv8-node-15.14.0.1-$(arch)-linux.gem && gem install libv8-node-15.14.0.1-$(arch)-linux.gem && rm libv8-node-15.14.0.1-$(arch)-linux.gem

RUN mkdir -p /app
WORKDIR /app

# Install gem dependencies prior to copying the entire application
COPY utils/build/docker/ruby/rails42/Gemfile .
COPY utils/build/docker/ruby/rails42/Gemfile.lock .
RUN bundle install

COPY utils/build/docker/ruby/rails42/ .
COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

ENV DD_TRACE_HEADER_TAGS=user-agent

ENV RAILS_ENV=production
ENV SECRET_KEY_BASE=e4d6dd9246d5d2fe497f8985074ca9bc698f6d889b8d1e04eb46442d439ff85a8ce3e5c8b776ed998d7be5d705a1069ec6a5999da0d5ca52f3c54f18cc2b7223
RUN bundle exec rake db:create db:migrate db:seed

RUN echo "#!/bin/bash\nbundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
