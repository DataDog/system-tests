FROM ghcr.io/datadog/images-rb/engines/ruby:2.7

RUN mkdir -p /app
WORKDIR /app

# Install gem dependencies prior to copying the entire application
COPY utils/build/docker/ruby/sinatra20/Gemfile .
COPY utils/build/docker/ruby/sinatra20/Gemfile.lock .
RUN sed -i -e '/gem .ddtrace./d' Gemfile && bundle config set --local without test development && bundle install

COPY utils/build/docker/ruby/sinatra20/ .
COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

ENV DD_TRACE_HEADER_TAGS=user-agent

RUN echo "#!/bin/bash\nbundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
