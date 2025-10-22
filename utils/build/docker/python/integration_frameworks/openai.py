import ddtrace.auto

import os

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="OpenAI framework library test server",
    description="""
The reference implementation of the OpenAI framework library test server.

Implement the API specified below to enable your framework to run all of the shared tests.
""",
)

import openai

client = openai.OpenAI(
    base_url=f"{os.getenv('DD_TRACE_AGENT_URL')}/vcr/openai"
)

class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[dict]
    parameters: dict

@app.post("/chat/completions")
def chat_completions(request: ChatCompletionRequest):
    stream = request.parameters.pop("stream", False)
    response = client.chat.completions.create(
        model=request.model,
        messages=request.messages,
        stream=stream,
        **request.parameters,
    )

    return {"response": response}