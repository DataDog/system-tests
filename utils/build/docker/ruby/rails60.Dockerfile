FROM ghcr.io/datadog/dd-trace-rb/ruby:2.7.6-dd

RUN apt-get update && apt-get install -y python2 && rm -rf /var/lib/apt/lists/*
RUN arch="$(arch | sed -e 's/x86_64/x64/' -e 's/aarch64/arm64/')" : \
 && curl -L -O https://nodejs.org/download/release/v12.22.12/node-v12.22.12-linux-${arch}.tar.gz \
 && tar -C /opt -xvzf node-v12.22.12-linux-${arch}.tar.gz \
 && rm -v node-v12.22.12-linux-${arch}.tar.gz \
 && echo 'export PATH="/opt/node-v12.22.12-linux-'${arch}'/bin:$PATH"' > /etc/profile.d/node.sh
RUN . /etc/profile.d/node.sh && npm install -g yarn

RUN mkdir -p /app
WORKDIR /app

COPY utils/build/docker/ruby/rails60/ .
COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

RUN . /etc/profile.d/node.sh && yarn install --check-files

ENV DD_TRACE_HEADER_TAGS=user-agent

RUN bundle exec rails db:create db:migrate db:seed

RUN echo "#!/bin/bash\nbundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
