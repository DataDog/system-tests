from typing import Optional, Union

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

import anthropic

client = anthropic.Anthropic(base_url=f"{os.getenv('DD_TRACE_AGENT_URL')}/vcr/anthropic")


class CreateRequest(BaseModel):
    model: str
    messages: list[dict]
    parameters: dict
    stream_as_method: bool = False


@app.post("/create")
def create(request: CreateRequest):
    kwargs = {
        "model": request.model,
        "messages": request.messages,
        **request.parameters,
    }

    stream = request.parameters.get("stream", False)

    if request.stream_as_method:
        chunks = []
        with client.messages.stream(**kwargs) as stream:
            for chunk in stream.text_stream:
                chunks.append(chunk)
        response = chunks
    elif stream:
        del kwargs["stream"]
        response = client.messages.create(**kwargs)

        chunks = []
        for chunk in response:
            chunks.append(chunk)
        response = chunks
    else:
        response = client.messages.create(**kwargs)

    return {"response": response}
