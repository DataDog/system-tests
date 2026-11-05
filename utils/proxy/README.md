The `proxy` is a Man-in-the-middle proxy spying on the data flow between the libraries and the agent (and OpenTelemetry
traffic), and recording it in the logs folder. What is sent to the backend goes to the mocked backend
(`utils/mocked_backend`) instead. This folder contains scripts loaded by MITM proxy (<https://mitmproxy.org/>).
