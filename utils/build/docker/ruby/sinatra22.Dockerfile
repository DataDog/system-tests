FROM ghcr.io/datadog/images-rb/engines/ruby:3.4

RUN mkdir -p /app
WORKDIR /app

ENV DD_TRACE_HEADER_TAGS="user-agent"

COPY utils/build/docker/ruby/sinatra22/Gemfile* ./
RUN bundle install

COPY utils/build/docker/ruby/sinatra22/ .

COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

CMD [ "./app.sh" ]
