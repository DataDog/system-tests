# Mocked backend: history of the migration

Between September and November 2026, end-to-end scenarios moved from observing the Datadog backend through the proxy to a single **mocked backend**, standing in for the Datadog backend in its own container. This page explains why, what changed, and lists the pull requests.

## Inception

Initially, the setup was simple: the agent spoke to the backend through a proxy. The proxy was responsible for decoding the traffic. Period. It worked for years. But slowly, different use cases made things a little bit more complex:

* The backend's determinism is tuned for Datadog production, not for testing. A 30-minutes ingestion time is fine in production
* We also need to get the data back from the backend?
* The backend can be down: what happens to the agent in such a situation? We need to start patching backend responses
* SSI starts to use the backend directly
* Oh, remote config: we definitely need to mock backend responses
* and many other corner cases
* FFE wants to use parametric tests with agentless, so it needs a lightweight thread mocking the backend
* and they also want to use it in end-to-end tests, which is understandable: they don't want two different APIs
* Wait, what, agentless? It means there is no agent anymore, so no proxy after the agent. And many tracer features will need to support it
* The last nail in the coffin: [#7607](https://github.com/DataDog/system-tests/pull/7607) (agentless tracing). The initial feature was tested by routing the library's traffic through the proxy. Testing it without an agent required many shenanigans to avoid duplicating all assertions.

You guessed it: the initial design is a dead end, and entropy will keep growing indefinitely if we don't come up with a new design that handles all use cases.

## Before

What the agent (or an agentless library) sent to the backend was observed in up to five different ways, each solving the same problems (decoding payloads, answering like the backend, keeping some state) on its own:

* **The proxy between the agent and the backend** (mitmproxy, `utils/proxy`), read by `interfaces.agent`. The agent reached it with `DD_PROXY_HTTPS`, and it forwarded to the real backend (`datad0g.com`), or answered itself with mocked responses. Remote config was served to the agent by the proxy, without TLS (`DD_REMOTE_CONFIGURATION_NO_TLS`).
* **Some proxy-specific setups for OpenTelemetry.**
* **The real Datadog backend**, queried by the now deleted `interfaces.backend`: flaky, and it needs a real API key.
* **The FFE agentless backend**, a separate mock for the feature flagging agentless scenarios.
* **Proxy interfaces for agentless traffic** (`datadog_direct`, `datadog_sidecar`), with the libraries sending through a proxy they would not use in a customer setup.

Any request to an intake that was not mocked could silently reach the real `DD_SITE` with a fake key.

## After

* **One mocked backend** (`utils/mocked_backend`), run in its own container (`MockedBackendContainer`) when a scenario sets `mocked_backend=True`. What it receives is recorded in the logs folder and read by `interfaces.mocked_backend`, which has the same methods as `interfaces.agent`.
* **Like a customer setup**: it serves HTTPS on `mocked-backend.invalid`, which is the `DD_SITE` of its senders. The intake hostnames derived from it (`trace.agent.`, `config.`, `instrumentation-telemetry-intake.`, ...) are network aliases of its container, listed in `MockedBackendServer.tls_hostnames`. Its certificate is generated when it starts, signed by the mitmproxy CA the senders trust. The agent is only given `DD_SITE` (and its API key), no intake URL. A request to an intake that is not listed fails, as `.invalid` never resolves.
* **The sender is identified by its API key** (`FakeDatadogKey`): the agent, an agentless library and serverless-init each use their own, and `interfaces.mocked_backend.get_data(..., with_api_key=...)` filters on it.
* **Remote config**: the mocked backend serves the remote config backend by default (`MockedBackendServerRcMixin`). Tests send configs with `remote_config.send_state`, which sets them on the mocked backend when the agent polls it. See [Remote config](../edit/remote-config.md).
* **Responses can be controlled** with `MockedBackendResponse`, for the whole session or at runtime, like with the proxy.
* The library still talks to the agent through the proxy, read by `interfaces.library`: only what is sent to the backend moved.

## How it was done

This revamp was pretty big, and would probably have taken around 30 days. In this AI era, most of the work happened in under two weeks, with several agents working together: making PRs of a manageable size, babysitting the CI, addressing comments from other AIs, and at the end, doing most of the job.

## Pull requests

* Mocked backend features
  * [#7668](https://github.com/DataDog/system-tests/pull/7668) Introduce Mocked Backend V2, used by `APM_TRACING_E2E_SINGLE_SPAN`
  * [#8149](https://github.com/DataDog/system-tests/pull/8149) Make `utils/mocked_backend` runnable without the rest of `utils`
  * [#8152](https://github.com/DataDog/system-tests/pull/8152) Add a mocked backend client and entry point
  * [#8155](https://github.com/DataDog/system-tests/pull/8155) Run the mocked backend in its own container
  * [#8183](https://github.com/DataDog/system-tests/pull/8183) Add the agent interface methods to the mocked backend interface, and notify `wait_for`
  * [#8186](https://github.com/DataDog/system-tests/pull/8186) Prepare the mocked backend for agentless FFE traffic: API key filtering, HTTPS
  * [#8209](https://github.com/DataDog/system-tests/pull/8209) Support the agent v3 sketches intake payload
  * [#8212](https://github.com/DataDog/system-tests/pull/8212) Check the mocked backend network aliases on GitLab
  * [#8220](https://github.com/DataDog/system-tests/pull/8220) Gather the fake Datadog keys in a `StrEnum`
  * [#8223](https://github.com/DataDog/system-tests/pull/8223) Support `MockedBackendResponse` in the mocked backend, like the proxy
  * [#8259](https://github.com/DataDog/system-tests/pull/8259) Generate the mocked backend TLS certificate when it starts
* Migrate legacy features to the new design
  * [#7814](https://github.com/DataDog/system-tests/pull/7814) Unify the FFE and v2 backends (first step)
  * [#8137](https://github.com/DataDog/system-tests/pull/8137) Rename `interfaces.backend` to `interfaces.backend_legacy`
  * [#8143](https://github.com/DataDog/system-tests/pull/8143) Unify FFE and the mocked backend: a single `MockedBackendServer`
  * [#8147](https://github.com/DataDog/system-tests/pull/8147) Agentless scenarios reuse the mocked backend option
  * [#8156](https://github.com/DataDog/system-tests/pull/8156) Only configure `interfaces.backend_legacy` when an API key is required
  * [#8211](https://github.com/DataDog/system-tests/pull/8211) Send agentless FFE events to the mocked backend, always over TLS, on `mocked-backend.invalid`
  * [#8240](https://github.com/DataDog/system-tests/pull/8240) Rename dead and legacy features: `backend_v2` becomes `mocked_backend`
  * [#8254](https://github.com/DataDog/system-tests/pull/8254) Agent on the mocked backend: set `DD_SITE` instead of each intake URL
* Scenarios moved to the mocked backend
  * [#7738](https://github.com/DataDog/system-tests/pull/7738) `APM_TRACING_E2E_OTEL`
  * [#8177](https://github.com/DataDog/system-tests/pull/8177) `APM_TRACING_EFFICIENT_PAYLOAD`
  * [#8185](https://github.com/DataDog/system-tests/pull/8185) `OTLP_RUNTIME_METRICS`
  * [#8239](https://github.com/DataDog/system-tests/pull/8239) `DEBUGGER_TELEMETRY`: the mocked backend serves remote config
  * [#8253](https://github.com/DataDog/system-tests/pull/8253) The debugger scenarios and `TRACING_CONFIG_NONDEFAULT_4`: remote config sent through the mocked backend
  * [#8258](https://github.com/DataDog/system-tests/pull/8258) `PROFILING`
  * [#8275](https://github.com/DataDog/system-tests/pull/8275) The `TRACE_STATS_COMPUTATION*` scenarios
  * [#8277](https://github.com/DataDog/system-tests/pull/8277) The infra-disabled standalone scenarios
  * [#8280](https://github.com/DataDog/system-tests/pull/8280) `INTEGRATIONS`, `INTEGRATIONS_AWS` and `OTEL_INTEGRATIONS`
  * [#8276](https://github.com/DataDog/system-tests/pull/8276) (open) The agent-based `FEATURE_FLAGGING` scenarios
  * [#8282](https://github.com/DataDog/system-tests/pull/8282) (open) `IPV6`
* Related
  * [#8150](https://github.com/DataDog/system-tests/pull/8150) Run the FFE contract self-tests in `TEST_THE_TEST`
  * [#8165](https://github.com/DataDog/system-tests/pull/8165) Each scenario is defined in its own module, so changing one only runs it in the CI
  * [#8250](https://github.com/DataDog/system-tests/pull/8250) FFE direct shutdown: detect the priming capture without the watchdog latency
  * [#8257](https://github.com/DataDog/system-tests/pull/8257) and [#8261](https://github.com/DataDog/system-tests/pull/8261) Revert, then reapply, a debugger telemetry test merged at the same time as #8239
* Closed without merging: [#7756](https://github.com/DataDog/system-tests/pull/7756), [#8226](https://github.com/DataDog/system-tests/pull/8226) (port of #7607, replaced by merging `main` into it), [#8273](https://github.com/DataDog/system-tests/pull/8273) (remote config without an agent, kept in #7607), [#8279](https://github.com/DataDog/system-tests/pull/8279) (wildcard certificate), [#8281](https://github.com/DataDog/system-tests/pull/8281) (replaced by #8280)
