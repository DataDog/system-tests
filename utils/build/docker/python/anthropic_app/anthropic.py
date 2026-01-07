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
    extra_headers: Optional[dict]


StreamRequest = CreateRequest


@app.post("/create")
def create(request: CreateRequest):
    response = client.messages.create(
        model=request.model,
        messages=request.messages,
        **request.parameters,
    )

    if request.parameters.get("stream", False):
        chunks = []
        for chunk in response:
            chunks.append(chunk)
        response = chunks

    return {"response": response}


@app.post("/stream")
def stream(request: StreamRequest):
    with client.messages.stream(
        model=request.model,
        messages=request.messages,
        **request.parameters,
    ) as stream:
        chunks = []
        for chunk in stream.text_stream:
            chunks.append(chunk)
        response = chunks

    return {"response": response}
