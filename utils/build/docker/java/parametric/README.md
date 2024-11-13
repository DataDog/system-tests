# Java Parametric Test client

## Design

This application is based on Spring Boot and its web starter.
It bundles four controllers:

* One root controller general commands (`/trace` endpoint)
* One for the Datadog Tracing API (`/trace/span` endpoint)
* One for the Datadog Metrics API (`/trace/stats` endpoint)
* One for the OpenTelemetry Tracing API (`/trace/otel` endpoint)

Each controller has its own package and DTO classes.

### General commands

The only command support is `crash`, to test the crash tracking feature enabled in `run.sh`.

> [!NOTE]
> Getting tracer configuration is not supported as not exposed, even using internal APIs, making `config` command unsupported.

### Datadog Tracing API

As the Java client library does not have a public tracing API, this controller is served by the deprecated OpenTracing API.
Access to internal features, like `flush`, is done using internal API (`InternalTracer`), exposed on purpose for system tests.

> [!NOTE]
> Span links are not supported as they choose to not add their support to the deprecated OpenTracing API.

### Datadog Metrics API

Access to internal features, like `flush`, is done using internal API (`InternalTracer`), exposed on purpose for system tests.

### Datadog OpenTelemetry API
