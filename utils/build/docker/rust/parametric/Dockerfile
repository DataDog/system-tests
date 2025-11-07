FROM rust:1.84.1-slim-bookworm AS builder
WORKDIR /usr/app
COPY utils/build/docker/rust/parametric .
COPY utils/build/docker/rust/parametric/../install_ddtrace.sh ./binaries/ /binaries/
COPY utils/build/docker/rust/parametric/Cargo.toml /usr/app/
COPY utils/build/docker/rust/parametric/src /usr/app/

RUN apt-get update && apt-get install -y --no-install-recommends openssh-client git

RUN /binaries/install_ddtrace.sh

RUN \
    --mount=type=cache,target=/usr/app/target/ \
    --mount=type=cache,target=/usr/local/cargo/registry/ \
    cargo build --release && cp ./target/release/ddtrace-rs-client /usr/app

FROM debian:bookworm-slim AS final
COPY --from=builder /usr/app/ddtrace-rs-client /usr/app/ddtrace-rs-client
COPY --from=builder /usr/app/Cargo.lock /usr/app/Cargo.lock
COPY utils/build/docker/rust/parametric/system_tests_library_version.sh /usr/app/system_tests_library_version.sh
RUN mkdir /parametric-tracer-logs
WORKDIR /usr/app

CMD ["./ddtrace-rs-client"]