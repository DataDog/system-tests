# Weblogs

In system tests, **weblogs** are an abstraction that represents the HTTP infrastructure instrumented by a library. There are currently four types of weblogs:

* **End-to-end weblogs**, which are tested using end-to-end scenarios. They come in the form of a simple Docker container.
* **Parametric weblogs**, which are targeted by **PARAMETRIC** scenarios. They are also simple HTTP applications running in Docker containers and allow interaction with Datadog library SDKs.
* **OTel weblogs**, which ship OpenTelemetry libraries.
* **GraphQL weblogs**.

## In this section

- [End-to-end weblog spec](end-to-end_weblog.md) -- all endpoints and their expected behavior
- [GraphQL weblog](graphql_weblog.md) -- GraphQL-specific weblog details

## See also

- [Scenarios](../scenarios/README.md) -- the different test scenario types that use weblogs
- [Build](../../execute/build.md) -- how to build weblog images and select variants
- [Architecture overview](../architecture.md) -- how weblogs fit into the test architecture
- [Back to documentation index](../../README.md)
