FROM ghcr.io/datadog/dd-trace-rb/ruby:2.5.9-dd

RUN curl -O https://rubygems.org/downloads/libv8-node-15.14.0.1-$(arch)-linux.gem && gem install libv8-node-15.14.0.1-$(arch)-linux.gem && rm libv8-node-15.14.0.1-$(arch)-linux.gem

RUN mkdir -p /app
WORKDIR /app

COPY utils/build/docker/ruby/rails50/ .
COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

ENV DD_TRACE_HEADER_TAGS=user-agent

RUN bundle exec rails db:create db:migrate db:seed

RUN echo "#!/bin/bash\nbundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
