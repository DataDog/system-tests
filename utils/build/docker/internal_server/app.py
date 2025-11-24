import os
import signal

import fastapi
import fastapi.responses


app = fastapi.FastAPI()


@app.get("/", status_code=200, response_class=fastapi.responses.PlainTextResponse)
async def root():
    """Health check"""
    return ""


@app.get("/mirror/{status}", response_class=fastapi.responses.JSONResponse)
@app.trace("/mirror/{status}", response_class=fastapi.responses.JSONResponse)
@app.post("/mirror/{status}", response_class=fastapi.responses.JSONResponse)
@app.put("/mirror/{status}", response_class=fastapi.responses.JSONResponse)
async def mirror(status: int, request: fastapi.Request):
    """Mirror GET endpoint

    use path parameter status as status code and query parameters as headers
    """
    query = request.query_params
    try:
        body = await request.json()
    except Exception:
        body = None
    return fastapi.responses.JSONResponse({"status": "OK", "payload": body}, status_code=status, headers=query)


@app.get("/redirect", response_class=fastapi.responses.RedirectResponse)
async def redirect(request: fastapi.Request):
    """Redirect endpoint for testing API 10 with redirects"""
    query = request.query_params
    redirect_to = query.get("redirect_to", "/mirror/200")

    return fastapi.responses.RedirectResponse(url=redirect_to, status_code=302)


@app.get("/shutdown")
async def shutdown():
    os.kill(os.getpid(), signal.SIGTERM)
    return {"message": "shutting down"}
