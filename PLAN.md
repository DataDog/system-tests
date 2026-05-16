# Proxy-Owned UDS Agent Socket

## Summary

Move end-to-end UDS weblog trace transport from per-weblog `socat` processes into the central proxy. UDS weblogs keep using tracer auto-detection of `/var/run/datadog/apm.socket`; the proxy owns that socket and forwards traffic through its existing HTTP proxy path to the agent.

Lambda `socat` remains out of scope because it exposes the Lambda extension's container-local `127.0.0.1:8126`, which the central proxy cannot reach directly.

## Key Changes

- Add a Unix stream listener in `utils/proxy/core.py`.
  - Default socket: `/var/run/datadog/apm.socket`.
  - Optional env override: `PROXY_APM_RECEIVER_SOCKET`.
  - Remove stale socket on startup, create the parent directory, and set permissive socket permissions.
  - For each UDS connection, open a TCP connection to the proxy's local weblog port `8126` so existing mitmproxy logging and forwarding stay unchanged.

- Update container wiring in `utils/_context/containers.py`.
  - Mount one runtime host directory, `./<logs>/interfaces/test_agent_socket`, into both proxy and UDS weblog containers at `/var/run/datadog`.
  - For UDS weblogs, remove `DD_AGENT_HOST` and `DD_TRACE_AGENT_PORT` from the runtime environment so tracers keep testing automatic UDS discovery.
  - Keep `DD_APM_RECEIVER_SOCKET=/var/run/datadog/apm.socket` as the UDS marker and path.

- Clean up end-to-end UDS weblog images.
  - Remove `socat` installation, `UDS_WEBLOG=1`, `set-uds-transport.sh` copies, and startup calls from UDS variants under Java, Python, Node.js, Go, .NET, and Ruby.
  - Remove the now-unused UDS transport helper if no non-lambda references remain.
  - Keep Lambda `socat` references unchanged.

## Test Plan

- Static checks:
  - `rg "socat|set-uds-transport|UDS_WEBLOG" utils/build/docker` should only show intentional Lambda usage, if any.
  - `./format.sh`.

- Build representative UDS weblogs:
  - `./build.sh python -w uds-flask`
  - `./build.sh nodejs -w uds-express4`
  - `./build.sh java -w uds-spring-boot`
  - `./build.sh golang -w uds-echo`
  - `./build.sh dotnet -w uds`
  - Ruby UDS variants if credentials/images are available.

- Runtime smoke:
  - `TEST_LIBRARY=python WEBLOG_VARIANT=uds-flask ./run.sh tests/test_smoke.py::Test_Library::test_receive_request_trace`
  - Repeat for at least one non-Python UDS weblog.
  - Confirm `logs_*/interfaces/library` receives trace payloads and the proxy stdout reports the UDS listener.

## Assumptions

- Existing UDS weblogs all use `/var/run/datadog/apm.socket`; that remains the supported socket path for this change.
- This preserves UDS auto-detection semantics and does not switch to `DD_TRACE_AGENT_URL=unix://...`.
- Lambda `socat` cleanup is excluded by choice because it is a separate localhost-extension bridge problem.
