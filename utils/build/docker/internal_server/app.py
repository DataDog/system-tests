import os
import signal

import fastapi
import fastapi.responses



app = fastapi.FastAPI()

@app.get("/", status_code=200, response_class=fastapi.responses.PlainTextResponse)
async def root():
    """Health check"""
    return ""


@app.get("/mirror_get/{status}", response_class=fastapi.responses.JSONResponse)
async def mirror_get(status: int, request: fastapi.Request):
    """Mirror GET endpoint

    use path parameter status as status code and query parameters as headers
    """
    query = request.query_params
    return fastapi.responses.JSONResponse({"status": "OK"}, status_code=status, headers=query)


@app.post("/mirror_post/{status}", response_class=fastapi.responses.JSONResponse)
async def mirror_post(status: int, request: fastapi.Request):
    """Mirror GET endpoint

    use path parameter status as status code and query parameters as headers
    """
    query = request.query_params
    body = await request.json()
    return fastapi.responses.JSONResponse({"status": "OK", "payload": body}, status_code=status, headers=query)

@app.get("/shutdown")
async def shutdown():
    os.kill(os.getpid(), signal.SIGTERM)
    return {"message": "shutting down"}