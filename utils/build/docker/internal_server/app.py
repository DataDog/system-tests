import os
import signal
import urllib.parse

import fastapi
import fastapi.responses


app = fastapi.FastAPI()


async def parse_form_data(request: fastapi.Request):
    raw_body = await request.body()
    parsed_data = urllib.parse.parse_qs(raw_body.decode("utf-8"))
    body = {k: v[0] for k, v in parsed_data.items()}
    return body


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
async def checkout_sessions(request: fastapi.Request):
    """Mock for Stripe Checkout Session creation"""
    try:
        body = await parse_form_data(request)

        if body.get("mode") != "payment":
            return fastapi.responses.JSONResponse({"type": "invalid_request_error", "message": "mock supports only payment mode"}, status_code=400)

        if "line_items[1][quantity]" in body:
            return fastapi.responses.JSONResponse({"type": "invalid_request_error", "message": "mock supports only one product"}, status_code=400)
        
        if body.get("line_items[0][price_data][currency]") != "eur" or body.get("shipping_options[0][shipping_rate_data][fixed_amount][currency]") != "eur":
            return fastapi.responses.JSONResponse({"type": "invalid_request_error", "message": "mock supports only eur currency"}, status_code=400)

        if "shipping_options[1][shipping_rate_data]" in body:
            return fastapi.responses.JSONResponse({"type": "invalid_request_error", "message": "mock supports only one shipping option"}, status_code=400)

        if "shiping_options[0][shipping_rate_data][type]" in body and body.get("shiping_options[0][shipping_rate_data][type]") != "fixed_amount":
            return fastapi.responses.JSONResponse({"type": "invalid_request_error", "message": "mock supports only fixed_amount shipping option"}, status_code=400)

        unit_amount = int(body.get("line_items[0][price_data][unit_amount]"))
        quantity = int(body.get("line_items[0][quantity]"))

        subtotal = unit_amount * quantity
        
        if body.get("discounts[0][promotion_code]") or body.get("discounts[0][coupon]"):
            amount_discount = subtotal * 0.1 # hardcoded 10% discount

        amount_shipping = int(body.get("shipping_options[0][shipping_rate_data][fixed_amount][amount]"))

        amount_total = subtotal - amount_discount + amount_shipping

        return fastapi.responses.JSONResponse({
            "id": "cs_FAKE",
            "amount_total": amount_total,
            "client_reference_id": body.get("client_reference_id"),
            "currency": "eur",
            "customer_email": body.get("customer_email"),
            "discounts": [{
                "coupon": body.get("discounts[0][coupon]"),
                "promotion_code": body.get("discounts[0][promotion_code]"),
            }],
            "livemode": True,
            "total_details": {
                "amount_discount": amount_discount,
                "amount_shipping": amount_shipping,
            },
        }, status_code=200)
    except Exception as e:
        return fastapi.responses.JSONResponse({"type": "api_error", "message": str(e)}, status_code=500)


@app.post("/v1/payment_intents", response_class=fastapi.responses.JSONResponse)
async def payment_intents(request: fastapi.Request):
    """Mock for Stripe Payment Intent creation"""
    try:
        body = await parse_form_data(request)

        return fastapi.responses.JSONResponse({
            "id": "pi_FAKE",
            "amount": int(body.get("amount")),
            "currency": body.get("currency"),
            "livemode": True,
            "payment_method": body.get("payment_method"),
            "receipt_email": body.get("receipt_email"),
        }, status_code=200)
    except Exception as e:
        return fastapi.responses.JSONResponse({"type": "api_error", "message": str(e)}, status_code=500)


@app.get("/shutdown")
async def shutdown():
    os.kill(os.getpid(), signal.SIGTERM)
    return {"message": "shutting down"}
