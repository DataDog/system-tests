FROM ghcr.io/datadog/dd-trace-rb/ruby:3.0.3-dd

RUN apt-get update && apt-get install -y nodejs npm
RUN npm install -g yarn

COPY utils/build/docker/ruby/rails61/ .
COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

RUN yarn install --check-files

ENV DD_TRACE_HEADER_TAGS=user-agent

RUN echo "#!/bin/bash\nbundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
