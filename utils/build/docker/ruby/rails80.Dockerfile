FROM ghcr.io/datadog/images-rb/engines/ruby:3.4

RUN mkdir -p /app
WORKDIR /app

ENV RAILS_ENV="production"
ENV RAILS_MASTER_KEY="9d319c57ec128e905d9e2ce5742bf2de"
ENV BUNDLE_WITHOUT="development test"
ENV DD_TRACE_HEADER_TAGS="user-agent"

COPY utils/build/docker/ruby/rails80/Gemfile* ./
RUN bundle install

COPY utils/build/docker/ruby/rails80/ .
COPY utils/build/docker/ruby/shared/rails/ .

COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

RUN bundle exec rails db:prepare

CMD [ "./app.sh" ]
