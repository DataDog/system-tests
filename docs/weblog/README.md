# Weblogs

In system tests, **weblogs** are an abstraction that represents the HTTP infrastructure instrumented by a library. There are currently four types of weblogs:

* **End-to-end weblogs**, which are tested using end-to-end scenarios. They come in the form of a simple Docker container.
* **Parametric weblogs**, which are targeted by **PARAMETRIC** scenarios. They are also simple HTTP applications running in Docker containers and allow interaction with Datadog library SDKs.
* **OTel weblogs**, which ship OpenTelemetry libraries.
* **GraphQL weblogs**.
