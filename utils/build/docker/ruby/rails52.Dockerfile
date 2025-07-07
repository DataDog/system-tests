FROM ghcr.io/datadog/images-rb/engines/ruby:2.7

RUN curl -O https://rubygems.org/downloads/libv8-node-16.10.0.0-$(arch)-linux.gem && gem install libv8-node-16.10.0.0-$(arch)-linux.gem && rm libv8-node-16.10.0.0-$(arch)-linux.gem && gem install mini_racer:'0.6.2'

RUN mkdir -p /app
WORKDIR /app

# Install gem dependencies prior to copying the entire application
COPY utils/build/docker/ruby/rails52/Gemfile .
COPY utils/build/docker/ruby/rails52/Gemfile.lock .
RUN bundle install

COPY utils/build/docker/ruby/rails52/ .
COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

ENV DD_TRACE_HEADER_TAGS=user-agent

ENV RAILS_ENV=production
ENV RAILS_MASTER_KEY=9d319c57ec128e905d9e2ce5742bf2de
RUN bundle exec rails db:create db:migrate db:seed

RUN echo "#!/bin/bash\nbundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
