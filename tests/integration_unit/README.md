# APM Client library shared integration/unit tests

## Setup

### Requirements

- docker
- protobuf
- python interpreter 3.7 or later

## Development

In the root of the repo:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
SYSTEM_TEST_E2E=False CLIENTS_ENABLED=dotnet tests/integration_unit
```
