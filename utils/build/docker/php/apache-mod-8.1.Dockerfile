ARG PHP_VERSION=8.1
ARG VARIANT=release

FROM datadog/dd-appsec-php-ci:php-$PHP_VERSION-$VARIANT

ENV DD_TRACE_ENABLED=1
ENV DD_TRACE_GENERATE_ROOT_SPAN=1
ENV DD_TRACE_AGENT_FLUSH_AFTER_N_REQUESTS=0
ENV DD_TRACE_HEADER_TAGS=user-agent

EXPOSE 7777/tcp

ADD binaries* /binaries/
ADD utils/build/docker/php /tmp/php

RUN chmod +x /tmp/php/apache-mod/build.sh
RUN /tmp/php/apache-mod/build.sh
RUN rm -rf /tmp/php/

ADD utils/build/docker/php/apache-mod/entrypoint.sh /
WORKDIR /binaries
ENTRYPOINT []
RUN echo "#!/bin/bash\ndumb-init /entrypoint.sh" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
