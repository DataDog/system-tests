# Internals

All about system-tests deep internals. For those of you who are not afraid of getting dirty hands.

## Lifecycles

- [End-to-end lifecycle](end-to-end-life-cycle.md) -- how end-to-end scenarios start containers, run setups, and execute tests
- [Parametric lifecycle](parametric-life-cycle.md) -- how parametric scenarios execute

## Pytest and configuration

- [Pytest internals](pytest.md) -- log levels, pytest configuration, and output control
- [Requirements](requirements.md) -- internal dependency requirements

## Infrastructure and tooling

- [MITM certificate](recreating_MITM_certificate.md) -- how to recreate the proxy certificate
- [Protobuf files](recreating_protobuf_files.md) -- regenerating protobuf definitions
- [Core dump generation](generate-core-dump.md) -- generating core dumps for debugging

## Design and history

- [Async model revamp](revamp-asynchronous-model.md) -- documentation on the asynchronous model
- [History](history.md) -- historical context and evolution of system-tests
- [PR reviews](PR-reviews.md) -- pull request review guidelines

---

## See also

- [Architecture overview](../understand/architecture.md) -- high-level system-tests architecture
- [Scenarios](../understand/scenarios/README.md) -- the different test scenario types
- [Running tests](../execute/README.md) -- how to build and run scenarios
- [Back to documentation index](../README.md)
