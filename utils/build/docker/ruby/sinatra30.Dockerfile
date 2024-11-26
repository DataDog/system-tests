FROM ghcr.io/datadog/images-rb/engines/ruby:3.2

RUN mkdir -p /app
WORKDIR /app

COPY utils/build/docker/ruby/sinatra30/ .

COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

ENV DD_TRACE_HEADER_TAGS=user-agent

RUN echo "#!/bin/bash\nbundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
