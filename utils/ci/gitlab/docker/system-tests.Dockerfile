FROM registry.ddbuild.io/images/docker:29.4.0-noble AS builder
USER root

RUN apt update && apt upgrade -y
RUN apt install software-properties-common -y
RUN add-apt-repository ppa:deadsnakes/ppa -y

RUN clean-apt install \
    build-essential \
    ca-certificates \
    git \
    python3.12 \
    python3-pip \
    python3.12-venv \
    python3.12-dev

COPY . /system-tests
WORKDIR /system-tests
RUN ./build.sh -i runner

FROM registry.ddbuild.io/images/docker:29.4.0-noble
USER root

RUN apt update && apt upgrade -y
RUN apt install software-properties-common -y
RUN add-apt-repository ppa:deadsnakes/ppa -y

RUN clean-apt install \
    jq \
    ca-certificates \
    curl \
    git \
    python3.12 \
    python3.12-venv

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    clean-apt install nodejs

RUN npm install -g @datadog/datadog-ci

ARG TARGETARCH
RUN if [ "${TARGETARCH}" = "arm64" ]; then \
      curl --retry 10 -fsSLo awscliv2.zip https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip; \
    else \
      curl --retry 10 -fsSLo awscliv2.zip https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip; \
    fi && \
    unzip -q awscliv2.zip && \
    ./aws/install && \
    apt-get clean

COPY --from=registry.ddbuild.io/dd-sts:v0.1.4@sha256:1f4bc8861cca86b0c977ae70843990f9368f9b69dbfc4979cf5c515a97a3ea15 \
    /usr/local/bin/dd-sts /usr/local/bin/dd-sts

COPY --from=builder /system-tests/venv /system-tests/venv

WORKDIR /
