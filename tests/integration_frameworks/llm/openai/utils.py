from typing import Any

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "extract_student_info",
            "description": "Get the student information from the body of the input text",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the person"},
                    "major": {"type": "string", "description": "Major subject."},
                    "school": {
                        "type": "string",
                        "description": "The university name.",
                    },
                },
            },
        },
    }
]
