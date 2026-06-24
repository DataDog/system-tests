# Proxy-Owned UDS Agent Socket

## Summary

Move end-to-end UDS weblog trace and DogStatsD transport from per-weblog `socat` processes into the central proxy. UDS weblogs keep using default socket paths under `/var/run/datadog`; the proxy owns those sockets and forwards traffic through its existing proxy paths to the agent.

Lambda `socat` remains out of scope because it exposes the Lambda extension's container-local `127.0.0.1:8126`, which the central proxy cannot reach directly.

## Key Changes

- Add Unix socket listeners in `utils/proxy/core.py`.
  - APM Unix stream socket: `/var/run/datadog/apm.socket`.
  - DogStatsD Unix datagram socket: `/var/run/datadog/dsd.socket`.
  - Remove stale socket on startup, create the parent directory, and set permissive socket permissions.
  - For each APM UDS connection, open a TCP connection to the proxy's local weblog port `8126` so existing mitmproxy logging and forwarding stay unchanged.
  - For each DogStatsD UDS datagram, forward to the agent's DogStatsD UDP port.

- Update container wiring in `utils/_context/containers.py`.
  - Mount one runtime host directory, `./<logs>/interfaces/test_agent_socket`, into both proxy and UDS weblog containers at `/var/run/datadog`.
  - For UDS weblogs, remove `DD_AGENT_HOST`, `DD_TRACE_AGENT_PORT`, `DD_TRACE_AGENT_URL`, `DD_DOGSTATSD_HOST`, `DD_DOGSTATSD_PORT`, and `DD_DOGSTATSD_URL` from the runtime environment so tracers keep testing automatic UDS discovery and do not receive normal TCP/UDP agent routing.
  - Keep `DD_APM_RECEIVER_SOCKET=/var/run/datadog/apm.socket` and `DD_DOGSTATSD_SOCKET=/var/run/datadog/dsd.socket` as the UDS markers and paths.

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

- Existing UDS weblogs all use `/var/run/datadog/apm.socket` for APM and `/var/run/datadog/dsd.socket` for DogStatsD; those remain the supported socket paths for this change.
- This preserves UDS auto-detection semantics and does not switch to `DD_TRACE_AGENT_URL=unix://...`.
- Lambda `socat` cleanup is excluded by choice because it is a separate localhost-extension bridge problem.
