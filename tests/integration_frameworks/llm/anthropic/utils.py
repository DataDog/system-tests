from typing import Any

from utils import irrelevant, context


@irrelevant("anthropic" not in context.weblog_variant)
class BaseAnthropicTest: ...


TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_weather",
        "description": "Get the current weather in a given location",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. San Francisco, CA",
                }
            },
            "required": ["location"],
        },
    }
]
