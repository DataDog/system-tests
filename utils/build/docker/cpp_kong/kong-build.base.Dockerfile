# ubuntu:24.04 ships with cmake 3.28 (minimum version required by dd-trace-cpp).
# Install the tracer build toolchain once when publishing the base image, rather
# than in every weblog build. Fail if package indexes cannot be downloaded.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get -o APT::Update::Error-Mode=any -o Acquire::Retries=3 update \
 && apt-get install -y --no-install-recommends \
        ca-certificates cmake g++ make libcurl4-openssl-dev git jq curl unzip \
 && rm -rf /var/lib/apt/lists/*
