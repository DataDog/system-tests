ARG BASE_IMAGE

FROM ${BASE_IMAGE}
WORKDIR /app
COPY lib-injection/build/docker/nodejs/sample-app/ .
ENV HOME  /root
EXPOSE 18080

# We need pid 1 to be bash and to properly configure nvm
# doing this via `RUN` doesn't seem to work
COPY utils/build/ssi/nodejs/run.sh /app/
CMD /app/run.sh
