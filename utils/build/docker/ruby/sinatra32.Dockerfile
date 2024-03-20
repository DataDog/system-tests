FROM ghcr.io/datadog/dd-trace-rb/ruby:3.2.0-dd

RUN mkdir -p /app
WORKDIR /app

COPY utils/build/docker/ruby/sinatra32/ .

COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

ENV DD_TRACE_HEADER_TAGS=user-agent

RUN echo "#!/bin/bash\nbundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
