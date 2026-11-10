# Security smoke tests across SDK topologies

These end-to-end scenarios run the same product assertions against `interfaces.mocked_backend`:

| Scenario | API | Export | OTel semantics |
| --- | --- | --- | --- |
| `SECURITY_SMOKE` | Datadog | Datadog | off |
| `SECURITY_SMOKE_OTEL_SEMANTICS` | Datadog | Datadog | on |
| `SECURITY_SMOKE_OTEL_API` | OTel | Datadog | off |
| `SECURITY_SMOKE_OTEL_API_SEMANTICS` | OTel | Datadog | on |
| `SECURITY_SMOKE_OTLP` | Datadog | OTLP/DDOT | off |
| `SECURITY_SMOKE_OTLP_SEMANTICS` | Datadog | OTLP/DDOT | on |
| `SECURITY_SMOKE_OTEL_API_OTLP` | OTel | OTLP/DDOT | off |
| `SECURITY_SMOKE_DDOT` | OTel | OTLP/DDOT | on |

These are requested configurations, not a claim that every released SDK supports all eight. A semantics flag can be ignored, partially implemented, or force OTLP. The transport probe requires the selected export path; the conventions probe requires the selected HTTP method attribute before Agent translation (`http.method` off, `http.request.method` on). A fallback transport or ignored semantics flag fails rather than counting as coverage. Native export uses the regular Agent; OTLP uses bundled DDOT.

The shared [AppSec smoke tests](../../../tests/appsec/smoke_tests/utils.py) cover WAF detection, RASP, telemetry, remote configuration, API schemas, and user events. [Additional probes](../../../tests/appsec/smoke_tests/test_security.py) cover IAST weak-hash reports, SCA dependency inventory, and AI Guard evaluation and blocking with existing VCR cassettes. Product availability follows the library manifests; these scenarios do not add missing security implementations to a language.

Backend tag checks require the resolved `http.client_ip`; peer metadata may use `network.client.ip` or `network.peer.address`. Synthetic k9appsec probes confirmed that a peer address alone does not populate the AppSec client IP, while an explicit `http.client_ip` works with either peer carrier. HTTP method/status must still reach intake as backend-compatible Datadog fields; putting OTel HTTP attributes directly into native metadata did not create these aliases in the live backend.

Backend tag checks cover event metadata (service, environment, HTTP method/status, client IP, user agent, WAF/rules versions, and WAF timings), blocking flags, RASP timings/evaluation counts, and exploit stacks linked to their trigger IDs. API Security probes check the request header, query, path, body, cookie, and JWT schema tags, plus response header/body schemas and the method/status/route used to identify the endpoint. These are representative values for every schema carrier, not exhaustive schema extraction tests.

Reports must arrive in an encoding the backend consumes. Structured reports must decode to objects. Base64 strings in ordinary metadata are rejected. API schemas must describe the request headers and retain the HTTP method. The assertions are identical for every topology. SDK exports are inspected only to verify the selected transport and HTTP conventions, never to reconstruct missing backend data.

This follows the [backend intake mapper](https://github.com/DataDog/dd-go/blob/main/trace/intake/events/mapper.go), which decodes MessagePack in `MetaStruct` separately from ordinary `Meta` tags. The [Agent OTLP mapper](https://github.com/DataDog/datadog-agent/blob/main/pkg/trace/transform/transform.go) and [SDK OTLP encoder](https://github.com/DataDog/libdatadog/blob/main/libdd-trace-utils/src/otlp_encoder/mapper.rs) are the conversion points to inspect when structured reports do not survive the DDOT path.

Where the selected weblog implements the OTel propagation API, its propagated trace ID must match the backend attack trace. PHP Apache, Ruby Rails 8, and Go net/http with Orchestrion currently lack this endpoint; their API-context probes are explicitly incomplete. This check does not replace the broader [parametric interoperability tests](../../../tests/parametric/test_otel_api_interoperability.py).

Each topology also has a `*_RUNTIME_ACTIVATION` variant. It runs only the activation smoke probe, starting without `DD_APPSEC_ENABLED` and with IAST disabled, as in the existing runtime activation scenario. Signed `ASM_FEATURES` configuration travels from the mocked backend through the Agent. The probe checks initial inactivity, activation and acknowledgement, an attack report at backend intake, then deactivation and absence of reports on a trace that still arrives. Configuration is cleared after the probe. These small variants keep activation independent from the main battery's explicitly enabled AppSec process.

## Bounded matrix

Weblog metadata opts in one framework per language: Python Flask, Java Spring Boot, Node.js Express 5, Go net/http with Orchestrion, .NET POC, Ruby Rails 8, and PHP Apache 8.2. All eight rows are selected for each language, including SDKs without OTLP or semantic-mode support, so unsupported combinations remain observable as configuration/transport failures. Unsupported products remain explicit in manifests. PHP's inventory probe checks the existing Composer fixture; Ruby checks Bundler after a normal request. Select the `security_smoke` and `security_smoke_runtime_activation` groups, or individual scenario names; these scenarios do not expand every framework combination.

## Run

The runner requires Python 3.12 and the ordinary [end-to-end prerequisites](../../../README.md). For example:

```sh
./build.sh python -w flask-poc
./run.sh SECURITY_SMOKE -L python --weblog flask-poc
./run.sh SECURITY_SMOKE_OTEL_API -L python --weblog flask-poc
./run.sh SECURITY_SMOKE_DDOT -L python --weblog flask-poc
./run.sh SECURITY_SMOKE_RUNTIME_ACTIVATION -L python --weblog flask-poc
./run.sh SECURITY_SMOKE_OTEL_API_RUNTIME_ACTIVATION -L python --weblog flask-poc
./run.sh SECURITY_SMOKE_DDOT_RUNTIME_ACTIVATION -L python --weblog flask-poc
```

DDOT uses `datadog/agent:latest-full`. To test a custom compatible full image, put its image reference in `binaries/ddot-agent-image`. The regular Agent keeps its existing `binaries/agent-image` override. The DDOT configuration disables the regular Agent's OTLP receiver so the bundled Collector owns port 4318. Node.js and .NET export HTTP/JSON; the other selected SDKs use HTTP/protobuf.

The mocked backend retains HTTPS and its normal certificate trust. Dependency inventory and remote configuration keep their Agent connection. The inventory probe requires a known application dependency with its version; it does not validate backend CVE matching. RC smoke inputs are published by the mocked backend and fetched through the Agent; the older standalone smoke scenarios keep their existing tracer-side RC fixture. AI Guard evaluation uses deterministic VCR responses; its resulting report must still reach trace intake. Passing these probes establishes the intake contract, not final processing or visibility in the live Datadog backend.

## Exploratory CI matrix

Dispatch the existing **Testing the test** workflow with `security_smoke_matrix=true`. It uses released libraries, the seven weblogs above, both smoke groups, and `force_execute=tests/appsec/smoke_tests/test_security.py`. This removes product activation skips/xfails for the exploratory run. Every scenario still runs after an earlier scenario fails. Normal caller runs retain manifest declarations. The forced run can fail for absent weblog endpoints and unsupported SDK modes as well as product regressions; inspect the transport/conventions probes before interpreting product passes as coverage.
