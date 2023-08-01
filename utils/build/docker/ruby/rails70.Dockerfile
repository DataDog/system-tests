FROM ghcr.io/datadog/dd-trace-rb/ruby:3.1.1-dd

RUN apt-get update && apt-get install -y nodejs npm

RUN mkdir -p /app
WORKDIR /app

COPY utils/build/docker/ruby/rails70/ .
COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

ENV DD_TRACE_HEADER_TAGS=user-agent

RUN bundle exec rails db:create db:migrate db:seed

RUN echo "#!/bin/bash\nbundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
