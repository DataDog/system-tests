# Java Parametric Test client

## Design

This application is based on Spring Boot and its web starter.
It bundles three controllers:

* One for the Datadog Tracing API (`trace/span`)
* One for the Datadog Metrics API (`trace/stats`)
* One for the OpenTelemetry Tracing API (`trace/otel`)

Each controller has its own package and DTO classes.

### Datadog Tracing API

As the Java client library does not have a public tracing API, this controller is served by the deprecated OpenTracing API.
Access to internal features, like `flush`, is done using internal API (`InternalTracer`), exposed on purpose for system tests.

> [!NOTE]
> Span links are not supported as they choose to not add their support to the deprecated OpenTracing API.

> [!NOTE]
> Getting tracer configuration is not supported as not exposed, even using internal APIs.

### Datadog Metrics API

Access to internal features, like `flush`, is done using internal API (`InternalTracer`), exposed on purpose for system tests.

### Datadog OpenTelemetry API

