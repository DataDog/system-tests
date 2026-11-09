# Security smoke tests across SDK topologies

These end-to-end scenarios run the same product assertions against `interfaces.mocked_backend`:

| Scenario | SDK API mode | Trace path |
| --- | --- | --- |
| `SECURITY_SMOKE` | Datadog | Native Datadog export through the Agent |
| `SECURITY_SMOKE_OTEL_API` | OTel bridge enabled | Native Datadog export through the Agent |
| `SECURITY_SMOKE_DDOT` | OTel bridge and semantics enabled | OTLP through bundled DDOT and its Datadog exporter |

The shared [AppSec smoke tests](../../../tests/appsec/smoke_tests/utils.py) cover WAF detection, RASP, telemetry, remote configuration, API schemas, and user events. [Additional probes](../../../tests/appsec/smoke_tests/test_security.py) cover IAST weak-hash reports, SCA dependency inventory, and AI Guard evaluation and blocking with existing VCR cassettes. Product availability follows the library manifests; these scenarios do not add missing security implementations to a language.

Reports must arrive in an encoding the backend consumes. Structured reports must decode to objects. Base64 strings in ordinary metadata are rejected. API schemas must describe the request headers and retain the HTTP method. The assertions are identical for every topology. SDK exports are inspected only to verify the selected transport, never to reconstruct missing backend data.

This follows the [backend intake mapper](https://github.com/DataDog/dd-go/blob/main/trace/intake/events/mapper.go), which decodes MessagePack in `MetaStruct` separately from ordinary `Meta` tags. The [Agent OTLP mapper](https://github.com/DataDog/datadog-agent/blob/main/pkg/trace/transform/transform.go) and [SDK OTLP encoder](https://github.com/DataDog/libdatadog/blob/main/libdd-trace-utils/src/otlp_encoder/mapper.rs) are the conversion points to inspect when structured reports do not survive the DDOT path.

The OTel variants also call the weblog's OTel propagation API. The propagated trace ID must match the backend attack trace. This verifies an actual API interaction; it does not replace the broader [parametric interoperability tests](../../../tests/parametric/test_otel_api_interoperability.py).

## Bounded matrix

Weblog metadata opts in one framework per language: Python Flask, Java Spring Boot, Node.js Express 5, Go net/http with Orchestrion, .NET POC, Ruby Rails 8, and PHP Apache 8.2. Ruby and PHP do not opt into the DDOT scenario because their SDKs do not export OTLP traces. Unsupported products remain explicit in manifests. PHP's inventory probe is marked as an incomplete test app because the selected plain weblog has no dependency inventory fixture. Add a topology to a caller's scenario list or select the `open_telemetry`/`appsec` group to run it; these scenarios do not expand every framework combination.

## Run

The runner requires Python 3.12 and the ordinary [end-to-end prerequisites](../../../README.md). For example:

```sh
./build.sh python -w flask-poc
./run.sh SECURITY_SMOKE -L python --weblog flask-poc
./run.sh SECURITY_SMOKE_OTEL_API -L python --weblog flask-poc
./run.sh SECURITY_SMOKE_DDOT -L python --weblog flask-poc
```

DDOT uses `datadog/agent:latest-full`. To test a custom compatible full image, put its image reference in `binaries/ddot-agent-image`. The regular Agent keeps its existing `binaries/agent-image` override. The DDOT configuration disables the regular Agent's OTLP receiver so the bundled Collector owns port 4318. Node.js and .NET export HTTP/JSON; the other selected SDKs use HTTP/protobuf.

The mocked backend retains HTTPS and its normal certificate trust. Dependency inventory and remote configuration keep their Agent connection. The inventory probe requires a known application dependency with its version; it does not validate backend CVE matching. RC smoke inputs are published by the mocked backend and fetched through the Agent; the older standalone smoke scenarios keep their existing tracer-side RC fixture. AI Guard evaluation uses deterministic VCR responses; its resulting report must still reach trace intake. Passing these probes establishes the intake contract, not final processing or visibility in the live Datadog backend.
