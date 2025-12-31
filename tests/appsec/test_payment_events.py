import hmac
import json
import time

from utils import features, interfaces, scenarios, weblog

WEBHOOK_SECRET = b"whsec_FAKE"

def make_webhook_request(data, secret=WEBHOOK_SECRET):
    timestamp = int(time.time())
    jsonStr = json.dumps(data)
    payload = f"{timestamp}.{jsonStr}"

    signature = hmac.new(secret, payload.encode("utf-8"), "sha256").hexdigest()

    return weblog.post("/stripe/webhook", headers={
        "content-type": "application/json",
        "stripe-signature": f"t={timestamp},v1={signature}"
    }, data=jsonStr)

def assert_payment_event(request, validator):
    assert request.status_code == 200

    # make sure a stripe object was returned by the API
    # all mocked objects will have an id field like "xx_FAKE"
    assert "_FAKE\"" in request.text

    interfaces.library.validate_one_span(request, validator=validator)

def assert_no_payment_event(request, status_code):
    assert request.status_code == status_code

    def validator(span: dict):
        assert "appsec.events.payments.integration" not in span["meta"]

    interfaces.library.validate_all_spans(request, validator=validator)

@scenarios.default
@features.appsec_automated_payment_events
class Test_Automated_Payment_Events_Stripe:
    def setup_checkout_session(self):
        self.r = weblog.post("/stripe/create_checkout_session", json={
            "client_reference_id": "GabeN",
            "line_items": [
                {
                    "price_data": {
                        "currency": "eur",
                        "product_data": {
                            "name": "test",
                        },
                        "unit_amount": 100,
                    },
                    "quantity": 10,
                },
            ],
            "mode": "payment",
            "customer_email": "gaben@valvesoftware.com",
            "discounts": [{
                "coupon": "COUPEZ",
                "promotion_code": "promo_FAKE",
            }],
            "shipping_options": [{
                "shipping_rate_data": {
                    "display_name": "test",
                    "fixed_amount": {
                        "amount": 50,
                        "currency": "eur",
                    },
                    "type": "fixed_amount",
                },
            }],
        })

    def test_checkout_session(self):
        """R1"""
        def validator(span: dict):
            assert span["metrics"]["_sampling_priority_v1"] == 1
            assert span["meta"]["appsec.events.payments.integration"] == "stripe"
            assert span["meta"]["appsec.events.payments.creation.id"] == "cs_FAKE"
            assert span["metrics"]["appsec.events.payments.creation.amount_total"] == 950 # 100 * 10 * 0.9 + 50
            assert span["meta"]["appsec.events.payments.creation.client_reference_id"] == "GabeN"
            assert span["meta"]["appsec.events.payments.creation.currency"] == "eur"
            assert span["meta"]["appsec.events.payments.creation.customer_email"] == "gaben@valvesoftware.com"
            assert span["meta"]["appsec.events.payments.creation.discounts.coupon"] == "COUPEZ"
            assert span["meta"]["appsec.events.payments.creation.discounts.promotion_code"] == "promo_FAKE"
            assert span["metrics"]["appsec.events.payments.creation.livemode"] == 1
            assert span["metrics"]["appsec.events.payments.creation.total_details.amount_discount"] == 100
            assert span["metrics"]["appsec.events.payments.creation.total_details.amount_shipping"] == 50

            return True

        assert_payment_event(self.r, validator=validator)
    
    def setup_checkout_session_unsupported(self):
        self.r = weblog.post("/stripe/create_checkout_session", json={
            "client_reference_id": "GabeN",
            "line_items": [
                {
                    "price_data": {
                        "currency": "eur",
                        "product_data": {
                            "name": "test",
                        },
                        "unit_amount": 100,
                    },
                    "quantity": 10,
                },
            ],
            "mode": "subscription", # unsupported mode
            "customer_email": "gaben@valvesoftware.com",
            "discounts": [{
                "coupon": "COUPEZ",
                "promotion_code": "promo_FAKE",
            }],
            "shipping_options": [{
                "shipping_rate_data": {
                    "display_name": "test",
                    "fixed_amount": {
                        "amount": 50,
                        "currency": "eur",
                    },
                    "type": "fixed_amount",
                },
            }],
        })

    def test_checkout_session_unsupported(self):
        """R1.1"""
        assert_no_payment_event(self.r, 200)

    def setup_payment_intent(self):
        self.r = weblog.post("/stripe/create_payment_intent", json={
            "amount": 6969,
            "currency": "eur",
            "payment_method": "pm_FAKE",
            "receipt_email": "gaben@valvesoftware.com",
        })

    def test_payment_intent(self):
        """R2"""
        def validator(span: dict):
            assert span["metrics"]["_sampling_priority_v1"] == 1
            assert span["meta"]["appsec.events.payments.integration"] == "stripe"
            assert span["meta"]["appsec.events.payments.creation.id"] == "pi_FAKE"
            assert span["metrics"]["appsec.events.payments.creation.amount"] == 6969
            assert span["meta"]["appsec.events.payments.creation.currency"] == "eur"
            assert span["metrics"]["appsec.events.payments.creation.livemode"] == 1
            assert span["meta"]["appsec.events.payments.creation.payment_method"] == "pm_FAKE"
            assert span["meta"]["appsec.events.payments.creation.receipt_email"] == "gaben@valvesoftware.com"

            return True

        assert_payment_event(self.r, validator=validator)

    def setup_payment_success(self):
        self.r = make_webhook_request({
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_FAKE",
                    "amount": 420,
                    "currency": "eur",
                    "livemode": True,
                    "payment_method": "pm_FAKE",
                },
            },
        })

    def test_payment_success(self):
        """R3"""
        def validator(span: dict):
            assert span["metrics"]["_sampling_priority_v1"] == 1
            assert span["meta"]["appsec.events.payments.integration"] == "stripe"
            assert span["meta"]["appsec.events.payments.success.id"] == "pi_FAKE"
            assert span["metrics"]["appsec.events.payments.success.amount"] == 420
            assert span["meta"]["appsec.events.payments.success.currency"] == "eur"
            assert span["metrics"]["appsec.events.payments.success.livemode"] == 1
            assert span["meta"]["appsec.events.payments.success.payment_method"] == "pm_FAKE"

            return True

        assert_payment_event(self.r, validator=validator)

    def setup_payment_failure(self):
        self.r = make_webhook_request({
            "type": "payment_intent.payment_failed",
            "data": {
                "object": {
                    "id": "pi_FAKE",
                    "amount": 1337,
                    "currency": "eur",
                    "last_payment_error": {
                        "code": "card_declined",
                        "decline_code": "stolen_card",
                        "payment_method": {
                            "id": "pm_FAKE",
                            "billing_details": {
                                "email": "gaben@valvesoftware.com",
                            },
                            "type": "card",
                        },
                    },
                    "livemode": True,
                },
            },
        })

    def test_payment_failure(self):
        """R4"""
        def validator(span: dict):
            assert span["metrics"]["_sampling_priority_v1"] == 1
            assert span["meta"]["appsec.events.payments.integration"] == "stripe"
            assert span["meta"]["appsec.events.payments.failure.id"] == "pi_FAKE"
            assert span["metrics"]["appsec.events.payments.failure.amount"] == 1337
            assert span["meta"]["appsec.events.payments.failure.currency"] == "eur"
            assert span["meta"]["appsec.events.payments.failure.last_payment_error.code"] == "card_declined"
            assert span["meta"]["appsec.events.payments.failure.last_payment_error.decline_code"] == "stolen_card"
            assert span["meta"]["appsec.events.payments.failure.last_payment_error.payment_method.id"] == "pm_FAKE"
            assert span["meta"]["appsec.events.payments.failure.last_payment_error.payment_method.billing_details.email"] == "gaben@valvesoftware.com"
            assert span["meta"]["appsec.events.payments.failure.last_payment_error.payment_method.type"] == "card"
            assert span["metrics"]["appsec.events.payments.failure.livemode"] == 1

            return True

        assert_payment_event(self.r, validator=validator)

    def setup_payment_cancellation(self):
        self.r = make_webhook_request({
            "type": "payment_intent.canceled",
            "data": {
                "object": {
                    "id": "pi_FAKE",
                    "amount": 1337,
                    "cancellation_reason": "requested_by_customer",
                    "currency": "eur",
                    "livemode": True,
                    "receipt_email": "gaben@valvesoftware.com",
                },
            },
        })

    def test_payment_cancellation(self):
        """R5"""
        def validator(span: dict):
            assert span["metrics"]["_sampling_priority_v1"] == 1
            assert span["meta"]["appsec.events.payments.integration"] == "stripe"
            assert span["meta"]["appsec.events.payments.cancellation.id"] == "pi_FAKE"
            assert span["metrics"]["appsec.events.payments.cancellation.amount"] == 1337
            assert span["meta"]["appsec.events.payments.cancellation.cancellation_reason"] == "requested_by_customer"
            assert span["meta"]["appsec.events.payments.cancellation.currency"] == "eur"
            assert span["metrics"]["appsec.events.payments.cancellation.livemode"] == 1
            assert span["meta"]["appsec.events.payments.cancellation.receipt_email"] == "gaben@valvesoftware.com"

            return True

        assert_payment_event(self.r, validator=validator)

    def setup_wrong_signature(self):
        self.r = make_webhook_request({
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_FAKE",
                    "amount": 420,
                    "currency": "eur",
                    "livemode": True,
                },
            },
        }, b"WRONG_SECRET") # wrong signature secret 

    def test_wrong_signature(self):
        """R6.1"""
        assert_no_payment_event(self.r, 403)

    def setup_unsupported_event(self):
        self.r = make_webhook_request({
            "type": "payment_intent.created", # unsupported type
            "data": {
                "object": {
                    "id": "pi_FAKE",
                    "amount": 420,
                    "currency": "eur",
                    "livemode": True,
                },
            },
        })
    
    def test_unsupported_event(self):
        """R6.2"""
        assert_no_payment_event(self.r, 200)