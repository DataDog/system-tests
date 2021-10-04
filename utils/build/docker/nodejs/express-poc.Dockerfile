FROM node:14

# print versions
RUN node --version && npm --version && curl --version

WORKDIR /usr/app

# install hello-world app
RUN npm install express

# app
RUN echo 'const tracer = require("dd-trace").init({debug: true});' >> app.js
RUN echo 'const app = require("express")();' >> app.js
RUN echo '\n\
app.get("/", (req, res) => { console.log("Received a request"); res.send("Hello\\n") });\n\
app.get("/sample_rate_route/:i", (req, res) => res.send("OK"));\n\
' >> app.js
RUN echo 'app.listen(7777, "0.0.0.0",() => {\
    tracer.trace("init.service", () => {});\
    console.log("listening")\
});' >> app.js
EXPOSE 7777

# docker startup
RUN echo '#!/bin/sh' > app.sh
RUN echo 'node app.js' >> app.sh
RUN chmod +x app.sh
CMD ./app.sh

COPY utils/build/docker/nodejs/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

# Datadog setup
ENV DD_TRACE_SAMPLE_RATE=0.5

# docker build -f utils/build/docker/nodejs.datadog.Dockerfile -t test .
# docker run -ti -p 7777:7777 test
