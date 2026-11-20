# Integration Frameworks Testing

Integration frameworks testing is a mix of parametric library testing with weblogs for coordinating framework installation (e.g. LLM client frameworks like OpenAI, or DB client frameworks like Postgres).

## Running the tests

```bash
./build.sh python
./run.sh INTEGRATION_FRAMEWORKS -L python --weblog openai-py@2.0.0 tests/integration_frameworks/llm/openai/test_openai_apm.py -vv
```

which will run the tests for all frameworks.

## Generating cassettes

To generate cassettes for a given framework, run the following command, making sure to include the relevant weblog (e.g. `openai-py@2.0.0`):

```bash
./utils/scripts/generate-integration-framework-cassettes.sh --weblog openai-py@2.0.0
```

which will run the tests without caring about the test assertions, and will enforce proper API keys to generate the cassettes one time.

## Anthropic weblog: `POST /mcp/create`

Used by the AI Guard MCP tests (`tests/integration_frameworks/llm/anthropic/test_anthropic_ai_guard_mcp.py`). The weblog starts a stdio MCP echo server, calls `messages.create` with the request tools plus the tools of that server, then runs each MCP `tool_use` of the response on the server.

Request body:

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `model` | string | required | Model of the `messages.create` call. |
| `messages` | list | required | Messages of the `messages.create` call. |
| `parameters` | object | required | Extra `messages.create` arguments, such as `max_tokens`. |
| `tools` | list | `[]` | Tools sent next to the MCP tools of the echo server. |
| `command_path` | boolean | `false` | When `true`, the echo server is started with the absolute path of the `python` interpreter instead of the bare `python` command. |

The echo server is always started as `python -m integration_frameworks.mcp_echo_server --token <secret>` with a secret in its environment, so tests can check that neither reaches AI Guard.

Response: `{"response": <messages.create response>, "tool_results": [{"tool_use_id": ..., "content": ...}]}`. The endpoint returns HTTP 501 when the Anthropic SDK has no MCP helpers (`anthropic<0.84.0`), and HTTP 500 when `command_path` is set but no absolute path to `python` is found.
