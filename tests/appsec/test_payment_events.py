import hmac
import json
import time
from utils import interfaces, scenarios, weblog

WEBHOOK_SECRET = b'whsec_FAKE'

def make_webhook_request(data):
    timestamp = int(time.time())
    jsonStr = json.dumps(data)
    payload = f"{timestamp}.{jsonStr}"

    signature = hmac.new(WEBHOOK_SECRET, payload.encode("utf-8"), "sha256").hexdigest()

    return weblog.post("/stripe/webhook", headers={
        "content-type": "application/json",
        "stripe-signature": f"t={timestamp},v1={signature}"
    }, data=jsonStr)

@scenarios.default
@features.payment_events_stripe
class Test_Payment_Events_Stripe:
    def setup_checkout_session(self):
        self.r = weblog.post("/stripe/create_checkout_session", json={
            "client_reference_id": "superdiaz",
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
                "coupon": "J7BN15vk",
                "promotion_code": "promo_1SEBV4A8AZcqnBxYVOzXjPVu",
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
        def validator(span: dict):
            assert span["metrics"]["_sampling_priority_v1"] == 1
            assert span["meta"]["appsec.events.payments.integration"] == "stripe"
            assert span["meta"]["appsec.events.payments.creation.id"] == "cs_FAKE"
            assert span["metrics"]["appsec.events.payments.creation.amount_total"] == 1050
            assert span["meta"]["appsec.events.payments.creation.client_reference_id"] == "superdiaz"
            assert span["meta"]["appsec.events.payments.creation.currency"] == "eur"
            assert span["meta"]["appsec.events.payments.creation.customer_email"] == "gaben@valvesoftware.com"
            assert span["meta"]["appsec.events.payments.creation.discounts.coupon"] == "J7BN15vk"
            assert span["meta"]["appsec.events.payments.creation.discounts.promotion_code"] == "promo_1SEBV4A8AZcqnBxYVOzXjPVu"
            #appsec.events.payments.creation.discounts.coupon
            # appsec.events.payments.creation.discounts.promotion_code
            assert span["metrics"]["appsec.events.payments.creation.livemode"] == 1
            assert span["metrics"]["appsec.events.payments.creation.total_details.amount_discount"] == 0
            assert span["metrics"]["appsec.events.payments.creation.total_details.amount_shipping"] == 50

            return True

        interfaces.library.validate_one_span(self.r, validator=validator)
    
    def setup_payment_intent(self):
        self.r = weblog.post("/stripe/create_payment_intent", json={
            "amount": 6969,
            "currency": "eur",
            "payment_method": "pm_FAKE",
            "receipt_email": "gaben@valvesoftware.com",
        })

    def test_payment_intent(self):
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

        interfaces.library.validate_one_span(self.r, validator=validator)

    def setup_payment_success(self):
        self.r = make_webhook_request({
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_FAKE",
                    "amount": 1337,
                    "currency": "eur",
                    "livemode": True,
                    "payment_method": "pm_FAKE",
                },
            },
        })

    def test_payment_success(self):
        def validator(span: dict):
            assert span["metrics"]["_sampling_priority_v1"] == 1
            assert span["meta"]["appsec.events.payments.integration"] == "stripe"
            assert span["meta"]["appsec.events.payments.success.id"] == "pi_FAKE"
            assert span["metrics"]["appsec.events.payments.success.amount"] == 1337
            assert span["meta"]["appsec.events.payments.success.currency"] == "eur"
            assert span["metrics"]["appsec.events.payments.success.livemode"] == 1
            assert span["meta"]["appsec.events.payments.success.payment_method"] == "pm_FAKE"

            return True

        interfaces.library.validate_one_span(self.r, validator=validator)

    def setup_payment_failure(self):
        self.r = make_webhook_request({
            "type": "payment_intent.payment_failed",
            "data": {
                "object": {
                    "id": "pi_FAKE",
                    "amount": 1337,
                    "currency": "eur",
                    "livemode": True,
                    "payment_method": "pm_FAKE",
                },
            },
        })

    def test_payment_failure(self):
        def validator(span: dict):
            assert span["metrics"]["_sampling_priority_v1"] == 1
            assert span["meta"]["appsec.events.payments.integration"] == "stripe"
            assert span["meta"]["appsec.events.payments.success.id"] == "pi_FAKE"

            return True

        interfaces.library.validate_one_span(self.r, validator=validator)

    def setup_payment_cancellation(self):
        self.r = make_webhook_request({
            "type": "payment_intent.canceled",
            "data": {
                "object": {
                    "id": "pi_FAKE",
                    "amount": 1337,
                    "currency": "eur",
                    "livemode": True,
                    "payment_method": "pm_FAKE",
                },
            },
        })

    def test_payment_cancellation(self):
        def validator(span: dict):
            assert span["metrics"]["_sampling_priority_v1"] == 1
            assert span["meta"]["appsec.events.payments.integration"] == "stripe"
            assert span["meta"]["appsec.events.payments.success.id"] == "pi_FAKE"

            return True

        interfaces.library.validate_one_span(self.r, validator=validator)
