
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

# Build locale_init.so: sets LC_ALL from TEST_LOCALE at process startup via LD_PRELOAD
RUN apt-get update && apt-get install -y --no-install-recommends locales gcc \
    && echo "de_DE.UTF-8 UTF-8" >> /etc/locale.gen && locale-gen \
    && printf '#include <locale.h>\n#include <stdlib.h>\n__attribute__((constructor)) static void init_locale(void){const char*l=getenv("TEST_LOCALE");if(l&&*l)setlocale(LC_ALL,l);}' > /tmp/li.c \
    && gcc -shared -fPIC -o /locale_init.so /tmp/li.c \
    && rm /tmp/li.c && rm -rf /var/lib/apt/lists/*

 # In case of crash, give time to the sidecar to upload the crash report
CMD ["bash", "-c", "[ -n \"${TEST_LOCALE:-}\" ] && export LD_PRELOAD=/locale_init.so; php server.php ${SYSTEM_TESTS_EXTRA_COMMAND_ARGUMENTS:-} || sleep 2s"]
