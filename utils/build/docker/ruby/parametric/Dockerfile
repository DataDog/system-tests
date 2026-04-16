FROM --platform=linux/amd64 ruby:3.2.1-bullseye

WORKDIR /app
COPY utils/build/docker/ruby/parametric .
COPY utils/build/docker/ruby/parametric/../install_ddtrace.sh binaries* /binaries/
COPY utils/build/docker/ruby/parametric/system_tests_library_version.sh system_tests_library_version.sh
RUN bundle install
RUN /binaries/install_ddtrace.sh
COPY utils/build/docker/ruby/parametric/server.rb /app/
RUN mkdir /parametric-tracer-logs

# Build locale_init.so: sets LC_ALL from TEST_LOCALE at process startup via LD_PRELOAD
RUN apt-get update && apt-get install -y --no-install-recommends locales gcc \
    && echo "de_DE.UTF-8 UTF-8" >> /etc/locale.gen && locale-gen \
    && printf '#include <locale.h>\n#include <stdlib.h>\n__attribute__((constructor)) static void init_locale(void){const char*l=getenv("TEST_LOCALE");if(l&&*l)setlocale(LC_ALL,l);}' > /tmp/li.c \
    && gcc -shared -fPIC -o /locale_init.so /tmp/li.c \
    && rm /tmp/li.c && rm -rf /var/lib/apt/lists/*

CMD ["bash", "-c", "[ -n \"${TEST_LOCALE:-}\" ] && export LD_PRELOAD=/locale_init.so; exec bundle exec ruby server.rb"]