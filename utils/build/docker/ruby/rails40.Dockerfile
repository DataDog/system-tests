FROM ghcr.io/datadog/system-tests-apps-ruby/rails40:latest

COPY utils/build/docker/ruby/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

RUN echo "#!/bin/bash\nbundle exec thin start -p 7777" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
