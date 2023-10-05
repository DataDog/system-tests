import json

from ddtrace import Pin, tracer
from ddtrace.appsec import trace_utils as appsec_trace_utils
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

app = FastAPI()


_TRACK_CUSTOM_APPSEC_EVENT_NAME = "system_tests_appsec_event"


@app.get("/", response_class=PlainTextResponse)
async def root():
    return "Hello, World!"


@app.get("/sample_rate_route/<i>", response_class=PlainTextResponse)
async def sample_rate(i):
    return "OK"


@app.get("/waf", response_class=PlainTextResponse)
@app.post("/waf", response_class=PlainTextResponse)
@app.options("/waf", response_class=PlainTextResponse)
@app.get("/waf/", response_class=PlainTextResponse)
@app.post("/waf/", response_class=PlainTextResponse)
@app.options("/waf/", response_class=PlainTextResponse)
async def waf():
    return "Hello, World!\n"


@app.get("/waf/<path>", response_class=PlainTextResponse)
@app.post("/waf/<path>", response_class=PlainTextResponse)
@app.options("/waf/<path>", response_class=PlainTextResponse)
@app.get("/params/<path>", response_class=PlainTextResponse)
@app.post("/params/<path>", response_class=PlainTextResponse)
@app.options("/params/<path>", response_class=PlainTextResponse)
async def waf_params(path):
    return "Hello, World!\n"


@app.get("/tag_value/<tag_value>/<status_code>", response_class=PlainTextResponse)
@app.options("/tag_value/<tag_value>/<status_code>", response_class=PlainTextResponse)
async def tag_value(tag_value: str, status_code: int, request: Request):
    appsec_trace_utils.track_custom_event(
        tracer, event_name=_TRACK_CUSTOM_APPSEC_EVENT_NAME, metadata={"value": tag_value}
    )
    return PlainTextResponse("Value tagged", status_code=status_code, headers=request.query_params)


@app.post("/tag_value/<tag_value>/<status_code>")
async def tag_value_post(tag_value: str, status_code: int, request: Request):
    appsec_trace_utils.track_custom_event(
        tracer, event_name=_TRACK_CUSTOM_APPSEC_EVENT_NAME, metadata={"value": tag_value}
    )
    if tag_value.startswith(payload_in_response_body):
        raw_body = await request.body()
        json_body = json.loads(raw_body)
        return JSONResponse({"payload": json_body}, status_code=status_code, headers=request.query_params)
    return PlainTextResponse("Value tagged", status_code=status_code, headers=request.query_params)
