FROM ruby:2.7

RUN uname -r

RUN apt-get update
RUN apt-get install -y nodejs npm

# print versions
RUN ruby --version && curl --version && node --version
COPY utils/build/docker/ruby/rails52 /app

WORKDIR /app

COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

RUN cat Gemfile
RUN rails --version
RUN which rails

RUN rm -f db/*.sqlite3
RUN bundle exec rake db:create
RUN bundle exec rake db:migrate
RUN bundle exec rake db:seed

#app setup
ENV WEB_CONCURRENCY=0

# Datadog setup
ENV DD_TRACE_SAMPLE_RATE=0.5
ENV DD_TAGS='key1:val1, key2 : val2 '

CMD exec rails server -p 7777 -b 0.0.0.0
