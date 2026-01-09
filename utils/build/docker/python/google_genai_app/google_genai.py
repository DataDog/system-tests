from typing import Optional, Any

import os

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="Google GenAI framework library test server",
    description="""
The reference implementation of the Google GenAI framework library test server.

Implement the API specified below to enable your framework to run all of the shared tests.
""",
)

from google import genai

client = genai.Client(http_options={"base_url": f"{os.getenv('DD_TRACE_AGENT_URL')}/vcr/genai"})


class GenAiGenerateContentRequest(BaseModel):
    model: str
    contents: Any
    config: Optional[dict] = None


GenAiEmbedContentRequest = GenAiGenerateContentRequest


@app.post("/generate_content")
def genai_generate_content(req: GenAiGenerateContentRequest):
    config = req.config or {}
    stream = config.pop("stream", False)

    kwargs = {"model": req.model, "contents": req.contents, "config": config}

    if stream:
        response = []
        for chunk in client.models.generate_content_stream(**kwargs):
            response.append(chunk)
    else:
        response = client.models.generate_content(**kwargs)

    return {"response": response}


@app.post("/embed_content")
def genai_embed_content(req: GenAiEmbedContentRequest):
    config = req.config or {}
    response = client.models.embed_content(model=req.model, contents=req.contents, config=config)
    return {"response": response}
