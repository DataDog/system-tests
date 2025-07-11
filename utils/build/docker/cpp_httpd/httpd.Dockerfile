FROM debian:stable-slim

# Install dependencies
RUN apt-get update && \
    apt-get install -y apache2 curl jq unzip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir /app

# Apache configuration
RUN a2enmod rewrite
COPY utils/build/docker/cpp_httpd/app/apache-config.conf /etc/apache2/sites-available/000-default.conf
RUN sed -i s/80/7777/ /etc/apache2/ports.conf

# Apache Plugin setup
COPY binaries/ /binaries
COPY utils/build/docker/cpp_httpd/install_ddtrace.sh /binaries/install_ddtrace.sh
RUN /binaries/install_ddtrace.sh
RUN echo "LoadModule datadog_module /usr/lib/apache2/modules/mod_datadog.so" > /etc/apache2/mods-available/datadog.load
RUN a2enmod datadog

# Create C++ application
RUN echo "Hello world\n" > /app/index.html
WORKDIR /app
RUN echo "#!/bin/bash\napachectl -D FOREGROUND" > app.sh
RUN chmod +x app.sh

EXPOSE 7777

CMD ./app.sh
