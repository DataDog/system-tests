FROM ghcr.io/datadog/system-tests-apps-ruby/sinatra21:latest

COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

RUN echo "#!/bin/bash\nbundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1" > ./app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
