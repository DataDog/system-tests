from typing import Any

import os

from fastapi import FastAPI
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

app = FastAPI(
    title="LiteLLM framework library test server",
    description="""
The reference implementation of the LiteLLM framework library test server.

Implement the API specified below to enable your framework to run all of the shared tests.
""",
)

import litellm

API_BASE = f"{os.getenv('DD_TRACE_AGENT_URL')}/vcr/openai"
PROXY_SERVER_URL = "http://0.0.0.0:4000"


class LitellmRequest(BaseModel):
    model: str
    parameters: dict = {}
    use_router: bool = False
    use_async: bool = False
    proxied: bool = False


class ChatCompletionRequest(LitellmRequest):
    messages: list[dict]


class CompletionRequest(LitellmRequest):
    prompt: str


def _to_json(obj: Any) -> Any:  # noqa: ANN401
    return obj.model_dump() if hasattr(obj, "model_dump") else obj


async def _call(request: LitellmRequest, operation: str, path: str, inputs: dict) -> dict:
    body = {"model": request.model, **inputs, **request.parameters}
    kwargs = dict(body)
    if request.proxied:
        # The LiteLLM proxy server gives the client request to litellm in this argument.
        kwargs["proxy_server_request"] = {
            "url": f"{PROXY_SERVER_URL}{path}",
            "method": "POST",
            "headers": {"content-type": "application/json"},
            "body": body,
        }

    if request.use_router:
        target: Any = litellm.Router(
            model_list=[{"model_name": request.model, "litellm_params": {"model": request.model, "api_base": API_BASE}}]
        )
    else:
        target = litellm
        kwargs["api_base"] = API_BASE

    stream = request.parameters.get("stream", False)
    if request.use_async:
        response = await getattr(target, f"a{operation}")(**kwargs)
        if stream:
            response = [chunk async for chunk in response]
    else:

        def call() -> Any:  # noqa: ANN401
            result = getattr(target, operation)(**kwargs)
            return list(result) if stream else result

        response = await run_in_threadpool(call)

    if stream:
        return {"response": [_to_json(chunk) for chunk in response]}
    return {"response": _to_json(response)}


@app.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    return await _call(request, "completion", "/v1/chat/completions", {"messages": request.messages})


@app.post("/completions")
async def completions(request: CompletionRequest):
    return await _call(request, "text_completion", "/v1/completions", {"prompt": request.prompt})
