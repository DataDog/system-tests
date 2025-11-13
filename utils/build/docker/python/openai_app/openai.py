from typing import Union

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

client = openai.OpenAI(base_url=f"{os.getenv('DD_TRACE_AGENT_URL')}/vcr/openai")


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[dict]
    parameters: dict


class CompletionRequest(BaseModel):
    model: str
    prompt: str
    parameters: dict


class EmbeddingsRequest(BaseModel):
    model: str
    input: str


class ResponsesCreateRequest(BaseModel):
    model: str
    input: Union[str, list[dict]]
    parameters: dict


@app.post("/chat/completions")
def chat_completions(request: ChatCompletionRequest):
    response = client.chat.completions.create(
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


@app.post("/completions")
def completions(request: CompletionRequest):
    response = client.completions.create(
        model=request.model,
        prompt=request.prompt,
        **request.parameters,
    )

    return {"response": response}


@app.post("/embeddings")
def embeddings(request: EmbeddingsRequest):
    response = client.embeddings.create(
        model=request.model,
        input=request.input,
    )

    return {"response": response}


@app.post("/responses/create")
def responses_create(request: ResponsesCreateRequest):
    response = client.responses.create(
        model=request.model,
        input=request.input,
        **request.parameters,
    )

    if request.parameters.get("stream", False):
        chunks = []
        for chunk in response:
            chunks.append(chunk)

        response = chunks

    return {"response": response}
