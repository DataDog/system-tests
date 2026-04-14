# Internals

All about system-tests deep internals. For those of you who are not afraid of getting dirty hands.

## Lifecycles

- [End-to-end lifecycle](end-to-end-life-cycle.md) -- how end-to-end scenarios start containers, run setups, and execute tests
- Parametric lifecycle -- see [parametric scenario](../understand/scenarios/parametric.md#parametric-lifecycle)

## Infrastructure and tooling

- [MITM certificate](recreating_MITM_certificate.md) -- how to recreate the proxy certificate
- [Core dump generation](generate-core-dump.md) -- generating core dumps for debugging

### Recreating protobuf schemas

Protobuf definitions for the traces are taken from https://github.com/DataDog/datadog-agent/tree/master/pkg/trace/pb.

You can update it by running the job "Update agent protobuf deserializer".

## Design and history

- [Async model revamp](revamp-asynchronous-model.md) -- documentation on the asynchronous model
- [PR reviews](PR-reviews.md) -- pull request review guidelines

This repo is a fork from legacy Sqreen System tests. You can find [in the history](https://github.com/DataDog/system-tests/tree/b3db65d0b58bde5ed3ecd601b2dae0b8f4bb6f06) this repo when it was forked.

---

## See also

- [Architecture overview](../understand/architecture.md) -- high-level system-tests architecture
- [Scenarios](../understand/scenarios/README.md) -- the different test scenario types
- [Running tests](../execute/README.md) -- how to build and run scenarios
- [Back to documentation index](../README.md)
