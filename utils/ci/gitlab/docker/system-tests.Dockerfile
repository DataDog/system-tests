FROM registry.ddbuild.io/images/docker:20.10.13-jammy AS builder
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

FROM registry.ddbuild.io/images/docker:20.10.13-jammy
USER root

RUN apt update && apt upgrade -y
RUN apt install software-properties-common -y
RUN add-apt-repository ppa:deadsnakes/ppa -y

RUN clean-apt install \
    jq \
    ca-certificates \
    git \
    python3.12 \
    python3.12-venv

ARG TARGETARCH
RUN if [ "${TARGETARCH}" = "arm64" ]; then \
      curl --retry 10 -fsSLo awscliv2.zip https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip; \
    else \
      curl --retry 10 -fsSLo awscliv2.zip https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip; \
    fi && \
    unzip -q awscliv2.zip && \
    ./aws/install && \
    apt-get clean

COPY --from=builder /system-tests/venv /system-tests/venv

WORKDIR /
