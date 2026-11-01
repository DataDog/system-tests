ARG BASE_IMAGE

FROM ${BASE_IMAGE}
WORKDIR /app

# Copy package files first for better Docker layer caching
COPY lib-injection/build/docker/nodejs/sample-app/package*.json ./
COPY lib-injection/build/docker/nodejs/sample-app/.npmrc ./

# Depot npm mirror. Env overrides the copied .npmrc, which pins registry.npmjs.org.
ENV npm_config_registry=https://depot-read-api-npm.us1.ddbuild.io/internal/magicmirror/magicmirror/
ENV npm_config_replace_registry_host=npmjs
# Install dependencies with exact versions only if package.json exists
RUN if [ -f package.json ]; then \
      export NVM_DIR="/root/.nvm" && \
      . "$NVM_DIR/nvm.sh" && \
      npm ci --only=production --no-audit --no-fund --loglevel http; \
    fi

# Copy the rest of the application
COPY lib-injection/build/docker/nodejs/sample-app/ .
ENV HOME  /root
EXPOSE 18080

# We need pid 1 to be bash and to properly configure nvm
# doing this via `RUN` doesn't seem to work
COPY utils/build/ssi/nodejs/run.sh /app/
CMD /app/run.sh
