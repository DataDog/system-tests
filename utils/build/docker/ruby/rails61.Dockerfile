FROM ghcr.io/datadog/images-rb/engines/ruby:3.0

RUN apt-get update && apt-get install -y nodejs npm
RUN npm install -g yarn

COPY utils/build/docker/ruby/rails61/ .
COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

RUN for attempt in `seq 3`; do if yarn install --check-files; then exit 0; fi; sleep 5; done; exit 1

ENV DD_TRACE_HEADER_TAGS=user-agent
ENV RAILS_ENV=production
ENV RAILS_MASTER_KEY=9d319c57ec128e905d9e2ce5742bf2de
RUN bundle exec rails db:create db:migrate db:seed

RUN echo "#!/bin/bash\nbundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
