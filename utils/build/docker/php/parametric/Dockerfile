
# Build locale_init.so and generate de_DE locale on a clean Debian image.
# The dd-trace-ci PHP base image has restricted apt sources inaccessible from
# GitHub Actions (apt-get update exits 100), so we can't install packages there.
# Instead, compile everything in a throwaway debian:bookworm-slim stage and copy
# the results over — both images are Bookworm-based so the .so and locale are
# binary-compatible.
FROM debian:bookworm-slim AS locale-tools
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev locales \
    && echo "de_DE.UTF-8 UTF-8" >> /etc/locale.gen && locale-gen \
    && printf '#include <locale.h>\n#include <stdlib.h>\n__attribute__((constructor)) static void init_locale(void){const char*l=getenv("TEST_LOCALE");if(l&&*l)setlocale(LC_ALL,l);}' > /tmp/li.c \
    && gcc -shared -fPIC -o /locale_init.so /tmp/li.c

FROM datadog/dd-trace-ci:php-8.2_bookworm-6
RUN switch-php nts
WORKDIR /binaries
ENV DD_TRACE_CLI_ENABLED=1
ADD utils/build/docker/php/parametric/composer.json .
ADD utils/build/docker/php/parametric/composer.lock .
RUN composer install
ADD utils/build/docker/php/parametric/../common/install_ddtrace.sh .
COPY binaries /binaries
RUN NO_EXTRACT_VERSION=Y ./install_ddtrace.sh
RUN php -d error_reporting='' -r 'echo phpversion("ddtrace");' > SYSTEM_TESTS_LIBRARY_VERSION
ADD utils/build/docker/php/parametric/server.php .
# RUN mkdir /parametric-tracer-logs

# Copy locale_init.so and locale archive from the clean builder
COPY --from=locale-tools /locale_init.so /locale_init.so
COPY --from=locale-tools /usr/lib/locale/locale-archive /usr/lib/locale/locale-archive

 # In case of crash, give time to the sidecar to upload the crash report
CMD ["bash", "-c", "[ -n \"${TEST_LOCALE:-}\" ] && export LD_PRELOAD=/locale_init.so; php server.php ${SYSTEM_TESTS_EXTRA_COMMAND_ARGUMENTS:-} || sleep 2s"]
