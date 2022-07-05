FROM ghcr.io/datadog/system-tests-apps-ruby/rails32:latest

COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

ENV DD_TRACE_HEADER_TAGS=user-agent

RUN echo "#!/bin/bash\nbundle exec thin start -p 7777" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
