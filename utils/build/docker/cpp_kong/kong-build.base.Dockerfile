# ubuntu:24.04 ships with cmake 3.28 (minimum version required by dd-trace-cpp)
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Build stage of the kong weblog: install the toolchain once, so that weblog builds don't depend on the Ubuntu mirrors
RUN apt-get -o APT::Update::Error-Mode=any -o Acquire::Retries=3 update \
 && apt-get install -y --no-install-recommends \
        ca-certificates cmake g++ make libcurl4-openssl-dev git jq curl unzip \
 && rm -rf /var/lib/apt/lists/*
