FROM public.ecr.aws/docker/library/debian:bookworm-slim

ARG JETTY_VERSION=9.4.58.v20250814

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl findutils tar \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    JETTY_FILE="jetty-distribution-${JETTY_VERSION}.tar.gz"; \
    JETTY_URL="https://repo1.maven.org/maven2/org/eclipse/jetty/jetty-distribution/${JETTY_VERSION}/${JETTY_FILE}"; \
    curl -fsSL \
      --retry 5 \
      --retry-delay 5 \
      --retry-connrefused \
      -o "/tmp/${JETTY_FILE}" \
      "${JETTY_URL}"; \
    mkdir -p /opt/jetty-classpath; \
    tar -xzf "/tmp/${JETTY_FILE}" -C /tmp; \
    find "/tmp/jetty-distribution-${JETTY_VERSION}/lib" -iname '*.jar' -exec cp {} /opt/jetty-classpath/ \;; \
    rm -f /opt/jetty-classpath/jetty-jaspi*; \
    rm -rf "/tmp/${JETTY_FILE}" "/tmp/jetty-distribution-${JETTY_VERSION}"
