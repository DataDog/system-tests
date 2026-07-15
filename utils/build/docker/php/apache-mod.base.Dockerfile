ARG PHP_VERSION=8.0
ARG VARIANT=release

FROM datadog/dd-appsec-php-ci:php-$PHP_VERSION-$VARIANT

ENV DD_TRACE_ENABLED=1
ENV DD_TRACE_GENERATE_ROOT_SPAN=1
ENV DD_TRACE_AGENT_FLUSH_AFTER_N_REQUESTS=0
ENV DD_TRACE_HEADER_TAGS=user-agent

EXPOSE 7777/tcp

# build.sh only reads from these three subdirectories (see apache-mod/build.sh); keep
# this list in sync with it, since it drives the base-image content hash.
COPY apache-mod /tmp/php/apache-mod
COPY weblogs /tmp/php/weblogs
COPY common /tmp/php/common

RUN chmod +x /tmp/php/apache-mod/build.sh
RUN /tmp/php/apache-mod/build.sh
RUN rm -rf /tmp/php/

WORKDIR /binaries
ENTRYPOINT []
RUN echo "#!/bin/bash\ndumb-init /entrypoint.sh" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]

# docker build --progress=plain -f utils/build/docker/php/apache-mod.base.Dockerfile -t datadog/system-tests:apache-mod-8.0.base utils/build/docker/php
# docker push datadog/system-tests:apache-mod-8.0.base
