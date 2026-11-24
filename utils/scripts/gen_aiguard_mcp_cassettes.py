#!/usr/bin/env python3
"""Generate the hand-crafted VCR cassettes of the AI Guard OpenAI hosted MCP tests.

Covers tests/integration_frameworks/llm/openai/test_openai_ai_guard_mcp.py (RFC "AI Guard MCP tool
calls and extensible connection policies", Delivery 1). No real OpenAI or AI Guard call is needed.

The dd-apm-test-agent VCR proxy (ddapm_test_agent/vcr_proxy.py, _generate_cassette_name) resolves
a request to the cassette file

    <provider>/<test_name>_<safe_path>_<method>_<hash8>.json

where test_name is the pytest originalname sent by TestAgentAPI.vcr_context, safe_path is the
proxied path with every character other than [A-Za-z0-9.-] turned into "_" (aiguard/evaluate ->
aiguard_evaluate, openai/responses -> openai_responses), and

    hash8 = sha256(f"{path}:POST:{json.dumps(json.loads(body), sort_keys=True)}").hexdigest()[:8]

So the AI Guard cassette name is a fingerprint of the exact evaluate request body, mcp_servers
included: a tracer that sends a different body misses the cassette. The integration_frameworks
test agent runs with VCR_CI_MODE=1 (unless --generate-cassettes), so a miss is answered with an
HTTP 500 "Cassette ... not found while running in CI mode", without calling the upstream nor
writing a file. AI Guard auto-instrumentation fails open on that error: the LLM call goes on and
the ai_guard span only carries an AIGuardClientError. Every AI Guard cassette below therefore
returns a reason unique to its test and evaluation (prompt before the model call, response after
it), and the tests assert both, which turns a body mismatch of either evaluation into a failure.

The AI Guard cassettes carry the meta the python tracer sends from the openai-py weblog
({"service": "openai", "env": null}), which is part of the hashed body: another tracer sending a
different meta needs cassettes of its own.

Every expected AI Guard payload is authored below by hand from the RFC contract, not derived
from a tracer implementation.

Run from the repo root:  python3 utils/scripts/gen_aiguard_mcp_cassettes.py
Pass --check to report drift without writing anything (used by format.sh --check).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

CASSETTES_ROOT = Path("tests/integration_frameworks/utils/vcr-cassettes")
# Every cassette this script owns starts with this prefix, which is how stale ones are found.
# Provider-specific on purpose, so tests of other providers can own their own MCP cassettes.
OWNED_PREFIX = "test_ai_guard_openai_mcp_"

MODEL = "gpt-4.1"
# Matches the meta the python tracer sends from the openai-py weblog (see the existing
# test_openai_ai_guard.py cassettes).
AI_GUARD_META = {"service": "openai", "env": None}
LEAK_MARKER = "s3cr3t"


def server_id(key: str) -> str:
    """RFC server ID: mcp_ followed by the first 16 hex characters of sha256(key)."""
    return "mcp_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


# The RFC reference vector, checked on every run.
assert server_id("url|https://mcp.example.com") == "mcp_b77bc22583ac5006"

EXAMPLE_ID = server_id("url|https://mcp.example.com")
DROPBOX_ID = server_id("connector|connector_dropbox")

# The host canonicalization vectors of the RFC: server_label, configured server_url, the url origin
# reported in mcp_servers (None: omitted, the name key is used) and the expected ID. Every tracer
# tests the same vectors, so the IDs are written out rather than derived from a tracer.
HOST_VECTORS: list[tuple[str, str, str | None, str]] = [
    ("ipv4_number", "http://2130706433/mcp", "http://127.0.0.1", "mcp_bb3842ff8c77d25d"),
    ("ipv4_port", "http://127.0.0.1:8080/mcp", "http://127.0.0.1:8080", "mcp_b339e608ea2ddcc1"),
    ("ipv6", "http://[0:0::1]:9000/mcp", "http://[::1]:9000", "mcp_cc35033de8004f7e"),
    ("percent_host", "http://%65xample.com/mcp", "http://example.com", "mcp_35da95b0ebe35a00"),
    ("underscore_host", "http://my_server.example/mcp", "http://my_server.example", "mcp_2607363cabc2eebc"),
    ("idn_host", "http://bücher.example/mcp", None, "mcp_905c59cb4ec642b0"),
]
for _label, _url, _origin, _expected_id in HOST_VECTORS:
    assert server_id(f"url|{_origin}" if _origin else f"name|{_label}") == _expected_id, _label

EXAMPLE_SERVER = {
    "id": EXAMPLE_ID,
    "managed_by": "provider",
    "name": "example",
    "url": "https://mcp.example.com",
    "transport": "unknown",
    "tools": {"ask_question": "ask_question"},
}
DROPBOX_SERVER = {
    "id": DROPBOX_ID,
    "managed_by": "provider",
    "name": "dropbox",
    "transport": "unknown",
    "tools": {"search": "search"},
}

EXAMPLE_TOOL = {
    "type": "mcp",
    "server_label": "example",
    "server_url": "https://mcp.example.com/mcp",
    "require_approval": "never",
}
# Userinfo, a path token, a query and a fragment, plus credentials in headers and authorization:
# none of it may reach AI Guard.
EXAMPLE_TOOL_WITH_SECRETS = {
    "type": "mcp",
    "server_label": "example",
    "server_url": (
        "https://user:s3cr3t-userinfo@MCP.Example.com:443/mcp/s3cr3t-path-token?token=s3cr3t-query#s3cr3t-fragment"
    ),
    "require_approval": "never",
    "headers": {"Authorization": "Bearer s3cr3t-header"},
}
DROPBOX_TOOL = {
    "type": "mcp",
    "server_label": "dropbox",
    "connector_id": "connector_dropbox",
    "authorization": "s3cr3t-oauth-token",
    "require_approval": "never",
}
WEATHER_TOOL = {
    "type": "function",
    "name": "get_weather",
    "description": "Get the current weather of a city",
    "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
}

ASK_QUESTION_ARGUMENTS = '{"question":"What is the AI Guard MCP RFC about?"}'
ASK_QUESTION_OUTPUT = "It describes how AI Guard evaluates MCP tool calls."
SEARCH_ARGUMENTS = '{"query":"quarterly report"}'
SEARCH_OUTPUT = "Found 1 file: Q3-report.pdf"
WEATHER_ARGUMENTS = '{"city":"Paris"}'


def _mcp_list_tools(item_id: str, label: str, tool_name: str) -> dict:
    return {
        "id": item_id,
        "type": "mcp_list_tools",
        "server_label": label,
        "tools": [
            {
                "name": tool_name,
                "description": f"The {tool_name} tool",
                "input_schema": {"type": "object", "properties": {}},
                "annotations": None,
            }
        ],
        "error": None,
    }


def _mcp_call(item_id: str, label: str, name: str, arguments: str, output: str) -> dict:
    return {
        "id": item_id,
        "type": "mcp_call",
        "approval_request_id": None,
        "arguments": arguments,
        "error": None,
        "name": name,
        "output": output,
        "server_label": label,
        "status": "completed",
    }


def _assistant_tool_call(call_id: str, name: str, arguments: str, mcp_server_id: str | None) -> dict:
    tool_call: dict = {"id": call_id, "function": {"name": name, "arguments": arguments}}
    if mcp_server_id is not None:
        tool_call["mcp"] = {"server_id": mcp_server_id}
    return {"role": "assistant", "tool_calls": [tool_call]}


def _mcp_call_turns(item_id: str, name: str, arguments: str, output: str, mcp_server_id: str | None) -> list[dict]:
    return [
        _assistant_tool_call(item_id, name, arguments, mcp_server_id),
        {"role": "tool", "tool_call_id": item_id, "content": output},
    ]


def _evaluation(action: str, reason: str, tags: list[str], *, blocking: bool) -> dict:
    return {
        "action": action,
        "reason": reason,
        "tags": tags,
        "tag_probs": None,
        "global_prob": 0.5 if action != "ALLOW" else 0.001,
        "is_blocking_enabled": blocking,
    }


def prompt_reason(test_name: str) -> str:
    """Reason returned only by the cassette of the exact expected prompt evaluation of test_name."""
    return f"system-tests MCP prompt matched: {test_name}"


def response_reason(test_name: str) -> str:
    """Reason returned only by the cassette of the exact expected response evaluation of test_name."""
    return f"system-tests MCP response matched: {test_name}"


_PROMPT = "Ask the example MCP server what the AI Guard MCP RFC is about."

LOOKUP_ARGUMENTS = '{"query":"AI Guard"}'
LOOKUP_OUTPUT = "AI Guard evaluates MCP tool calls."
READ_DOCS_ARGUMENTS = '{"page":"rfc"}'
READ_DOCS_OUTPUT = "The RFC defines the MCP server ID."


def _vector_tool(label: str, url: str) -> dict:
    return {"type": "mcp", "server_label": label, "server_url": url, "require_approval": "never"}


def _vector_server(label: str, origin: str | None, expected_id: str) -> dict:
    server: dict = {"id": expected_id, "managed_by": "provider", "name": label}
    if origin is not None:
        server["url"] = origin
    server["transport"] = "unknown"
    server["tools"] = {f"{label}_lookup": f"{label}_lookup"}
    return server


# Same origin, different paths: one server ID, so one mcp_servers entry named after the first label,
# with the tools of both labels.
EXAMPLE_SSE_TOOL = {
    "type": "mcp",
    "server_label": "example_sse",
    "server_url": "https://mcp.example.com/sse",
    "require_approval": "never",
}

# test name -> scenario. request is what the test sends to the weblog POST /responses/create
# (input and model, plus the tools parameter), output is the OpenAI response output, and
# guard_messages / mcp_servers are the expected AI Guard evaluation of the response.
SCENARIOS: dict[str, dict] = {
    "test_ai_guard_openai_mcp_call_server_url": {
        "input": _PROMPT,
        "tools": [EXAMPLE_TOOL],
        "output": [
            _mcp_list_tools("mcpl_system_tests_1", "example", "ask_question"),
            _mcp_call("mcp_system_tests_1", "example", "ask_question", ASK_QUESTION_ARGUMENTS, ASK_QUESTION_OUTPUT),
        ],
        "guard_messages": _mcp_call_turns(
            "mcp_system_tests_1", "ask_question", ASK_QUESTION_ARGUMENTS, ASK_QUESTION_OUTPUT, EXAMPLE_ID
        ),
        "mcp_servers": [EXAMPLE_SERVER],
        "verdict": "ALLOW",
    },
    "test_ai_guard_openai_mcp_call_server_url_sanitized": {
        "input": _PROMPT,
        "tools": [EXAMPLE_TOOL_WITH_SECRETS],
        "output": [
            _mcp_call("mcp_system_tests_2", "example", "ask_question", ASK_QUESTION_ARGUMENTS, ASK_QUESTION_OUTPUT),
        ],
        "guard_messages": _mcp_call_turns(
            "mcp_system_tests_2", "ask_question", ASK_QUESTION_ARGUMENTS, ASK_QUESTION_OUTPUT, EXAMPLE_ID
        ),
        "mcp_servers": [EXAMPLE_SERVER],
        "verdict": "ALLOW",
    },
    "test_ai_guard_openai_mcp_call_connector": {
        "input": "Search my dropbox for the quarterly report.",
        "tools": [DROPBOX_TOOL],
        "output": [
            _mcp_call("mcp_system_tests_3", "dropbox", "search", SEARCH_ARGUMENTS, SEARCH_OUTPUT),
        ],
        "guard_messages": _mcp_call_turns("mcp_system_tests_3", "search", SEARCH_ARGUMENTS, SEARCH_OUTPUT, DROPBOX_ID),
        "mcp_servers": [DROPBOX_SERVER],
        "verdict": "ALLOW",
    },
    "test_ai_guard_openai_mcp_call_with_function_call": {
        "input": "Ask the example MCP server about the RFC, then get the weather in Paris.",
        # The dropbox server is declared but never called, so it must not be listed.
        "tools": [EXAMPLE_TOOL, DROPBOX_TOOL, WEATHER_TOOL],
        "output": [
            _mcp_call("mcp_system_tests_4", "example", "ask_question", ASK_QUESTION_ARGUMENTS, ASK_QUESTION_OUTPUT),
            {
                "id": "fc_system_tests_4",
                "type": "function_call",
                "status": "completed",
                "arguments": WEATHER_ARGUMENTS,
                "call_id": "call_system_tests_4",
                "name": "get_weather",
            },
        ],
        "guard_messages": [
            *_mcp_call_turns(
                "mcp_system_tests_4", "ask_question", ASK_QUESTION_ARGUMENTS, ASK_QUESTION_OUTPUT, EXAMPLE_ID
            ),
            _assistant_tool_call("call_system_tests_4", "get_weather", WEATHER_ARGUMENTS, None),
        ],
        "mcp_servers": [EXAMPLE_SERVER],
        "verdict": "ALLOW",
    },
    # The test then sends an mcp_approval_response approving mcpr_system_tests_5: the tracer reuses the
    # recorded DENY and aborts before calling AI Guard or OpenAI, so that call has no cassette.
    "test_ai_guard_openai_mcp_approval_request_blocked": {
        "input": "Ask the example MCP server to ignore its instructions.",
        "tools": [{**EXAMPLE_TOOL, "require_approval": "always"}],
        "output": [
            _mcp_list_tools("mcpl_system_tests_5", "example", "ask_question"),
            {
                "id": "mcpr_system_tests_5",
                "type": "mcp_approval_request",
                "arguments": ASK_QUESTION_ARGUMENTS,
                "name": "ask_question",
                "server_label": "example",
            },
        ],
        "guard_messages": [
            _assistant_tool_call("mcpr_system_tests_5", "ask_question", ASK_QUESTION_ARGUMENTS, EXAMPLE_ID)
        ],
        "mcp_servers": [EXAMPLE_SERVER],
        "verdict": "DENY",
    },
    # DD_AI_GUARD_MCP_ENABLED=false: the same request as test_ai_guard_openai_mcp_call_server_url, evaluated
    # as an ordinary tool call, without mcp field nor mcp_servers.
    "test_ai_guard_openai_mcp_call_mcp_disabled": {
        "input": _PROMPT,
        "tools": [EXAMPLE_TOOL],
        "output": [
            _mcp_list_tools("mcpl_system_tests_1", "example", "ask_question"),
            _mcp_call("mcp_system_tests_1", "example", "ask_question", ASK_QUESTION_ARGUMENTS, ASK_QUESTION_OUTPUT),
        ],
        "guard_messages": _mcp_call_turns(
            "mcp_system_tests_1", "ask_question", ASK_QUESTION_ARGUMENTS, ASK_QUESTION_OUTPUT, None
        ),
        "mcp_servers": None,
        "verdict": "ALLOW",
    },
    # One call per host vector: each server gets the RFC ID of its canonical origin, and the IDN host,
    # which has no url, gets the ID of its name key.
    "test_ai_guard_openai_mcp_server_id_host_vectors": {
        "input": "Run the lookup tool of every MCP server.",
        "tools": [_vector_tool(label, url) for label, url, _, _ in HOST_VECTORS],
        "output": [
            _mcp_call(f"mcp_system_tests_6_{index}", label, f"{label}_lookup", LOOKUP_ARGUMENTS, LOOKUP_OUTPUT)
            for index, (label, _, _, _) in enumerate(HOST_VECTORS)
        ],
        "guard_messages": [
            turn
            for index, (label, _, _, expected_id) in enumerate(HOST_VECTORS)
            for turn in _mcp_call_turns(
                f"mcp_system_tests_6_{index}", f"{label}_lookup", LOOKUP_ARGUMENTS, LOOKUP_OUTPUT, expected_id
            )
        ],
        "mcp_servers": [_vector_server(label, origin, expected_id) for label, _, origin, expected_id in HOST_VECTORS],
        "verdict": "ALLOW",
    },
    "test_ai_guard_openai_mcp_servers_sharing_an_id_merge": {
        "input": "Ask the example MCP server about the RFC, then read its docs.",
        "tools": [EXAMPLE_TOOL, EXAMPLE_SSE_TOOL],
        "output": [
            _mcp_call("mcp_system_tests_7_0", "example", "ask_question", ASK_QUESTION_ARGUMENTS, ASK_QUESTION_OUTPUT),
            _mcp_call("mcp_system_tests_7_1", "example_sse", "read_docs", READ_DOCS_ARGUMENTS, READ_DOCS_OUTPUT),
        ],
        "guard_messages": [
            *_mcp_call_turns(
                "mcp_system_tests_7_0", "ask_question", ASK_QUESTION_ARGUMENTS, ASK_QUESTION_OUTPUT, EXAMPLE_ID
            ),
            *_mcp_call_turns("mcp_system_tests_7_1", "read_docs", READ_DOCS_ARGUMENTS, READ_DOCS_OUTPUT, EXAMPLE_ID),
        ],
        "mcp_servers": [{**EXAMPLE_SERVER, "tools": {"ask_question": "ask_question", "read_docs": "read_docs"}}],
        "verdict": "ALLOW",
    },
}


def cassette_name(test_name: str, path: str, body: str) -> str:
    """The file name the test-agent VCR proxy looks up for a POST of body to path."""
    details = f"{path}:POST:{json.dumps(json.loads(body), sort_keys=True)}"
    digest = hashlib.sha256(details.encode()).hexdigest()[:8]
    safe_path = "".join(c if c.isalnum() or c in ".-" else "_" for c in path)
    return f"{test_name}_{safe_path}_post_{digest}.json"


def _render(url: str, request_body: str, response_body: str, response_content_type: str) -> str:
    cassette = {
        "request": {
            "method": "POST",
            "url": url,
            "headers": {"Content-Type": "application/json"},
            "body": request_body,
        },
        "response": {
            "status": {"code": 200, "message": "OK"},
            "headers": {"content-type": response_content_type},
            "body": response_body,
        },
    }
    return json.dumps(cassette, indent=2) + "\n"


def _guard_cassette(test_name: str, attributes: dict, evaluation: dict) -> tuple[str, str]:
    request_body = json.dumps({"data": {"attributes": attributes}})
    response_body = json.dumps(
        {"data": {"id": f"system-tests-{test_name}", "type": "evaluations", "attributes": evaluation}}
    )
    name = cassette_name(test_name, "aiguard/evaluate", request_body)
    content = _render(
        "https://app.datadoghq.com/api/v2/ai-guard/evaluate", request_body, response_body, "application/vnd.api+json"
    )
    return f"aiguard/{name}", content


def _openai_cassette(test_name: str, scenario: dict, index: int) -> tuple[str, str]:
    request = {"input": scenario["input"], "model": MODEL, "tools": scenario["tools"]}
    request_body = json.dumps(request)
    # OpenAI echoes the tool declarations without their credentials.
    echoed_tools = [
        {key: value for key, value in tool.items() if key not in ("headers", "authorization")}
        for tool in scenario["tools"]
    ]
    response = {
        "id": f"resp_system_tests_{index}",
        "object": "response",
        "created_at": 1793836800,
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "instructions": None,
        "max_output_tokens": None,
        "model": "gpt-4.1-2025-04-14",
        "output": scenario["output"],
        "parallel_tool_calls": True,
        "previous_response_id": None,
        "reasoning": {"effort": None, "summary": None},
        "store": True,
        "temperature": 1.0,
        "text": {"format": {"type": "text"}},
        "tool_choice": "auto",
        "tools": echoed_tools,
        "top_p": 1.0,
        "truncation": "disabled",
        "usage": {
            "input_tokens": 120,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 30,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 150,
        },
        "user": None,
        "metadata": {},
    }
    response_body = json.dumps(response, indent=2)
    name = cassette_name(test_name, "openai/responses", request_body)
    return f"openai/{name}", _render(
        "https://api.openai.com/v1/responses", request_body, response_body, "application/json"
    )


def build_corpus() -> dict[str, str]:
    """Relative cassette path -> content, for every scenario."""
    contents: dict[str, str] = {}
    for index, (test_name, scenario) in enumerate(SCENARIOS.items(), start=1):
        assert test_name.startswith(OWNED_PREFIX), test_name
        user = {"role": "user", "content": scenario["input"]}

        # Before the model call: the prompt alone, which references no MCP server.
        prompt_attributes = {"messages": [user], "meta": AI_GUARD_META}
        prompt_evaluation = _evaluation("ALLOW", prompt_reason(test_name), [], blocking=False)
        path, content = _guard_cassette(test_name, prompt_attributes, prompt_evaluation)
        contents[path] = content

        # After the model call: prompt plus response, with the referenced MCP servers.
        attributes: dict = {"messages": [user, *scenario["guard_messages"]], "meta": AI_GUARD_META}
        if scenario["mcp_servers"] is not None:
            attributes["mcp_servers"] = scenario["mcp_servers"]
        request_body = json.dumps(attributes)
        assert LEAK_MARKER not in request_body, f"{test_name}: a credential would be sent to AI Guard"
        if scenario["verdict"] == "ALLOW":
            evaluation = _evaluation("ALLOW", response_reason(test_name), [], blocking=False)
        else:
            evaluation = _evaluation(scenario["verdict"], response_reason(test_name), ["jailbreak"], blocking=True)
        path, content = _guard_cassette(test_name, attributes, evaluation)
        assert path not in contents, f"{test_name}: prompt and response evaluations collide on {path}"
        contents[path] = content

        path, content = _openai_cassette(test_name, scenario, index)
        contents[path] = content
    return contents


def _owned_on_disk() -> set[str]:
    return {
        f"{provider}/{path.name}"
        for provider in ("aiguard", "openai")
        for path in (CASSETTES_ROOT / provider).glob(f"{OWNED_PREFIX}*.json")
    }


def main(argv: list[str]) -> int:
    check = "--check" in argv[1:]
    assert CASSETTES_ROOT.is_dir(), f"missing {CASSETTES_ROOT}; run from repo root"
    contents = build_corpus()
    orphans = sorted(_owned_on_disk() - set(contents))

    if check:
        differences = [f"{name} (would be deleted)" for name in orphans]
        for name, content in sorted(contents.items()):
            path = CASSETTES_ROOT / name
            if not path.is_file():
                differences.append(f"{name} (missing)")
            elif path.read_text() != content:
                differences.append(f"{name} (outdated)")
        if differences:
            print("AI Guard MCP cassettes are out of date:")
            for difference in differences:
                print(f"  {difference}")
            return 1
        print(f"{len(contents)} AI Guard MCP cassettes in sync")
        return 0

    for name, content in contents.items():
        (CASSETTES_ROOT / name).write_text(content)
    for orphan in orphans:
        (CASSETTES_ROOT / orphan).unlink()
        print(f"removed orphan cassette {orphan}")
    for name in sorted(contents):
        print(f"wrote {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
