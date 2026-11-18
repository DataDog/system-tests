from typing import Any, Optional, Union

import importlib.util
import os

from fastapi import FastAPI, HTTPException
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
async_client = anthropic.AsyncAnthropic(base_url=f"{os.getenv('DD_TRACE_AGENT_URL')}/vcr/anthropic")

# anthropic<0.84.0 has no MCP helpers; when they exist, mcp is installed and a broken install fails at startup.
MCP_HELPERS = importlib.util.find_spec("anthropic.lib.tools.mcp") is not None
if MCP_HELPERS:
    from anthropic.lib.tools.mcp import async_mcp_tool
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

# The env and the arguments after the module carry a secret marker that must never reach AI Guard.
MCP_ECHO_SERVER = dict(
    command="python",
    args=["-m", "integration_frameworks.mcp_echo_server", "--token", "s3cr3t-arg"],
    env={"MCP_TOKEN": "s3cr3t-env"},
)


class CreateRequest(BaseModel):
    model: str
    messages: list[dict]
    parameters: dict
    extra_headers: Optional[dict] = None


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


class McpCreateRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    parameters: dict[str, Any]
    tools: list[dict[str, Any]] = []


@app.post("/mcp/create")
async def mcp_create(request: McpCreateRequest):  # no return type: FastAPI would use it as response_model
    """messages.create with the tools of a stdio MCP echo server, then run each MCP tool_use of the response."""
    if not MCP_HELPERS:
        raise HTTPException(status_code=501, detail="this anthropic version has no MCP helpers")

    async with stdio_client(StdioServerParameters(**MCP_ECHO_SERVER)) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            mcp_tools = {tool.name: async_mcp_tool(tool, session) for tool in (await session.list_tools()).tools}
            response = await async_client.messages.create(
                model=request.model,
                messages=request.messages,
                tools=[*request.tools, *(tool.to_dict() for tool in mcp_tools.values())],
                **request.parameters,
            )
            tool_results = [
                {"tool_use_id": block.id, "content": await mcp_tools[block.name].call(block.input)}
                for block in response.content
                if block.type == "tool_use" and block.name in mcp_tools
            ]

    return {"response": response, "tool_results": tool_results}
