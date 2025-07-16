FROM ghcr.io/datadog/images-rb/engines/ruby:3.4

RUN mkdir -p /app
WORKDIR /app

ENV RAILS_ENV="production" \
  RAILS_MASTER_KEY="9d319c57ec128e905d9e2ce5742bf2de" \
  BUNDLE_WITHOUT="development test" \
  DD_TRACE_HEADER_TAGS="user-agent"

# Install gem dependencies prior to copying the entire application
COPY utils/build/docker/ruby/rails80/Gemfile utils/build/docker/ruby/rails80/Gemfile.lock ./
RUN bundle install

COPY utils/build/docker/ruby/rails80/ .
COPY utils/build/docker/ruby/shared/rails/ .

CMD [ "./app.sh" ]
