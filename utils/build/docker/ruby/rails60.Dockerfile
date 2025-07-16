FROM ghcr.io/datadog/images-rb/engines/ruby:2.7

RUN apt-get update && apt-get install -y nodejs npm
RUN npm install -g yarn

RUN mkdir -p /app
WORKDIR /app

# Install gem dependencies prior to copying the entire application
COPY utils/build/docker/ruby/rails60/Gemfile .
COPY utils/build/docker/ruby/rails60/Gemfile.lock .
RUN sed -i -e '/gem .ddtrace./d' Gemfile && bundle config set --local without test development && bundle install

COPY utils/build/docker/ruby/rails60/ .
COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

ENV DD_TRACE_HEADER_TAGS=user-agent
ENV RAILS_ENV=production
ENV RAILS_MASTER_KEY=9d319c57ec128e905d9e2ce5742bf2de
RUN bundle exec rails db:create db:migrate db:seed

RUN echo "#!/bin/bash\nbundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
