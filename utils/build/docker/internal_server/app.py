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
    """Redirect endpoint for testing API 10 with redirects

    Query parameter:
    - totalRedirects: number of redirects remaining (default 0)
    """
    query = request.query_params
    total_redirects = int(query.get("totalRedirects", "0"))

    if total_redirects > 0:
        # Redirect to itself with totalRedirects-1
        location = f"/redirect?totalRedirects={total_redirects - 1}"
    else:
        location = "/mirror/200"

    return fastapi.responses.RedirectResponse(url=location, status_code=302)


@app.post("/v1/checkout/sessions", response_class=fastapi.responses.JSONResponse)
async def checkoutSessions(request: fastapi.Request):
    return fastapi.responses.JSONResponse({
        "id": "cs_test_aaaaa",
        "amount_total": 406046392,
        "client_reference_id": "superdiaz",
        "currency": "eur",
        "customer_email": "a@b.c",
        "discounts": [
            {
                "coupon": "a",
                "promotion_code": "a"
            }
        ],
        "livemode": False,
        "total_details": {
            "amount_discount": 406046392,
            "amount_shipping": 406046392
        }
    }, status_code=200)


@app.get("/shutdown")
async def shutdown():
    os.kill(os.getpid(), signal.SIGTERM)
    return {"message": "shutting down"}
