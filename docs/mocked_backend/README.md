# Mocked backend

The mocked backend stands in for the Datadog backend in end-to-end scenarios. It runs in its own container, receives everything the agent (or a library without agent) sends to Datadog, records it, and answers like the real backend would. Tests read what it received with `interfaces.mocked_backend`.

For why it exists and how we got there, see the [history](history.md).

## Goal

One single way to observe what is sent to the Datadog backend, whatever the setup: a library with an agent, a library sending straight to the intake (agentless), serverless-init... It replaces the proxy between the agent and the backend, the real backend (flaky, needs a real API key), and the ad hoc mocks that each feature used to add.

## Design rules

1. **As close as possible to a customer setup.** When realism and convenience conflict, realism wins. The mocked backend serves HTTPS, senders reach it with the hostnames they derive from `DD_SITE`, and they trust its certificate like a real one. Senders get no proxy setting and no intake URL: the agent is only given `DD_SITE` and its API key.
2. **Fail closed.** Its domain, `mocked-backend.invalid`, uses the reserved `.invalid` TLD: a request to an intake the mocked backend doesn't serve fails, instead of silently reaching the real Datadog.
3. **The API key tells who sent a request.** The agent, an agentless library and serverless-init each use their own fake key (`FakeDatadogKey`). Tests filter on it (`with_api_key=...`), not on hostnames or paths, which differ between libraries.
4. **As little configuration as possible.** `DD_SITE` is enough for the agent. Adding an intake means adding its hostname to one list, `MockedBackendServer.tls_hostnames`.
5. **Standalone.** `utils/mocked_backend` only depends on `utils/proxy`, so it runs in its own container (the proxy image), in-process for parametric tests, or locally.
6. **Easy to migrate to.** `interfaces.mocked_backend` has the same methods as `interfaces.agent` (`get_traces`, `get_spans`, `get_metrics`, `get_telemetry_data`, `wait_for`...): a test usually only changes the interface it reads.

## Key features

* **Recording**: every request is decoded (gzip, zstd, chunked bodies, protobuf, msgpack, multipart...) and recorded in `logs_<scenario>/interfaces/mocked_backend/`, with the same format as the proxy recordings. Its own logs show one line per request, with its path and status code.
* **HTTPS on many hostnames**: `mocked-backend.invalid` and the intake hostnames derived from it (`trace.agent.`, `config.`, `instrumentation-telemetry-intake.`, `debugger-intake.`...) are network aliases of its container. Its certificate is generated when it starts, for all of them, signed by the mitmproxy CA (`utils/proxy/.mitmproxy`) the senders trust.
* **Remote config**: it serves the remote config backend by default (no config until a test sends one). Tests send configs with `remote_config.send_state`, which sets them on the mocked backend, then waits for the library to apply them. See [Remote config](../edit/remote-config.md).
* **Controlled responses**: `MockedBackendResponse` overrides the answer on a path, for the whole session (`MockedBackendContainer.internal_mocked_responses`) or at runtime (`client.set_mocked_responses`), like the proxy's mocked responses.
* **Feature flagging**: endpoints serving the agentless FFE configuration, with scripted responses (`client.ffe_set_response(s)`) and counters (`client.ffe_get_status`). The JSON configuration applies flag selection (`selected_flag_tags`, `selected_flag_key_patterns`) with the semantics of `ffe-system-test-data` `flag-selection/README.md`. `client.ffe_use_suite(name)` serves an `ffe-system-test-data` evaluation suite's UFC instead, matching tags from its `flag-tags.json`; `client.ffe_set_flag_selection_ignored_reason(...)` makes it ignore every valid, non-empty selection, as when production cannot load tags.
* **Control endpoints**: under `/system-tests/`, never recorded, used by `MockedBackendClient` from the test runner.

## Using it in a scenario

* With an agent: nothing to do, every end-to-end scenario uses it. The library still talks to the agent through the proxy (`interfaces.library`); what the agent sends to the backend is in `interfaces.mocked_backend`.
* Without an agent: the agentless scenarios (`utils/_context/_scenarios/agentless_endtoend.py`) set it up, with `DD_SITE` pointing to it.
* In tests: read `interfaces.mocked_backend`, and use the scenario's API key (e.g. `scenario.weblog_api_key`) to keep only what a given sender sent.
