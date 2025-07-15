# TODO: Pin base image using SHA256 digest for reproducible builds
# Note: ghcr.io/datadog/images-rb/engines/ruby:3.1 requires authentication to get SHA256 digest
# Manual action needed: Get SHA256 digest and replace with: FROM ghcr.io/datadog/images-rb/engines/ruby@sha256:DIGEST
FROM ghcr.io/datadog/images-rb/engines/ruby:3.1

RUN apt-get update && apt-get install -y nodejs npm

RUN mkdir -p /app
WORKDIR /app

# Install gem dependencies prior to copying the entire application
COPY utils/build/docker/ruby/rails70/Gemfile .
COPY utils/build/docker/ruby/rails70/Gemfile.lock .
RUN sed -i -e '/gem .ddtrace./d' Gemfile && bundle config set --local without test development && bundle install

COPY utils/build/docker/ruby/rails70/ .
COPY utils/build/docker/ruby/shared/rails/ .
COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

ENV DD_TRACE_HEADER_TAGS=user-agent
ENV RAILS_ENV=production
ENV RAILS_MASTER_KEY=9d319c57ec128e905d9e2ce5742bf2de
RUN bundle exec rails db:create db:migrate db:seed

RUN echo "#!/bin/bash\nbundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
