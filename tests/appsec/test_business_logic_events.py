from utils import scenarios
from utils import weblog
from utils import interfaces


@scenarios.stripe
class Test_Business_Logic_Events_Stripe:
    def setup_checkout_session(self):
        self.r = weblog.post("/stripe/create_checkout_session", json={
            "client_reference_id": "superdiaz",
            "line_items": [
                {
                    "price_data": {
                        "currency": "eur",
                        "product_data": {
                            "name": "test"
                        },
                        "unit_amount": 100
                    },
                    "quantity": 100
                }
            ],
            "mode": "payment",
            "customer_email": "topkek@topkek.com",
            "discounts": [{
                # "coupon": "J7BN15vk",
                "promotion_code": "promo_1SEBV4A8AZcqnBxYVOzXjPVu"
            }],
            "shipping_options": [{
                "shipping_rate_data": {
                    "display_name": "test",
                    "fixed_amount": {
                        "amount": 100,
                        "currency": "eur"
                    },
                    "type": "fixed_amount"
                }
            }]
        })

    def test_checkout_session(self):
        def validator(span: dict):
            assert span["metrics"]["_sampling_priority_v1"] == 1
            assert span["meta"]["appsec.events.payments.integration"] == "stripe"
            assert span["meta"]["appsec.events.payments.creation.id"] == "cs_test_aaaaa"
            assert span["metrics"]["appsec.events.payments.creation.amount_total"] == 406046392
            assert span["meta"]["appsec.events.payments.creation.client_reference_id"] == "superdiaz"
            assert span["meta"]["appsec.events.payments.creation.currency"] == "eur"
            assert span["meta"]["appsec.events.payments.creation.customer_email"] == "a@b.c"
            # appsec.events.payments.creation.discounts.coupon
            # appsec.events.payments.creation.discounts.promotion_code
            assert span["metrics"]["appsec.events.payments.creation.livemode"] == 0
            assert span["metrics"]["appsec.events.payments.creation.total_details.amount_discount"] == 406046392
            assert span["metrics"]["appsec.events.payments.creation.total_details.amount_shipping"] == 406046392

            return True

        interfaces.library.validate_one_span(self.r, validator=validator)
    
    def setup_payment_intent(self):
        self.r = weblog.post("/stripe/create_payment_intent", json={
            "amount": 6900,
            "currency": "eur",
            # //confirm: true,
            "description": "is it the description",
            "receipt_email": "topkek@topkek.com",
            "shipping": {
                "address": {
                    "city": "Condom",
                    "country": "FR",
                    "line1": "Impasse des deux jambes",
                    "postal_code": "69000",
                },
                "name": "Email-Hugo",
                "carrier": "Le groupe DPD",
                "phone": "+33123456789",
                "tracking_number": "01172000"
            }
        })

    def test_payment_intent(self):
        def validator(span: dict):
            assert span["metrics"]["_sampling_priority_v1"] == 1
            assert span["meta"]["appsec.events.payments.integration"] == "stripe"
            assert span["meta"]["appsec.events.payments.creation.id"] == "cs_test_aaaaa"
            assert span["metrics"]["appsec.events.payments.creation.amount_total"] == 406046392
            assert span["meta"]["appsec.events.payments.creation.client_reference_id"] == "superdiaz"
            assert span["meta"]["appsec.events.payments.creation.currency"] == "eur"
            assert span["meta"]["appsec.events.payments.creation.customer_email"] == "a@b.c"
            # appsec.events.payments.creation.discounts.coupon
            # appsec.events.payments.creation.discounts.promotion_code
            assert span["metrics"]["appsec.events.payments.creation.livemode"] == 0
            assert span["metrics"]["appsec.events.payments.creation.total_details.amount_discount"] == 406046392
            assert span["metrics"]["appsec.events.payments.creation.total_details.amount_shipping"] == 406046392

            # appsec.events.payments.creation.amount
            # appsec.events.payments.creation.payment_method
            # appsec.events.payments.creation.receipt_email

            return True

        interfaces.library.validate_one_span(self.r, validator=validator)

    def setup_payment_success(self):
        self.r = weblog.post("/stripe/webhook", headers={"stripe-signature": "t=1337,v1=HARDCODED_SIGNATURE"}, json={
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "aaa",
                    "amount": 1337,
                    "currency": "eur",
                    "livemode": False,
                    "payment_method": "blabla"
                }
            }
        })

    def test_payment_success(self):
        def validator(span: dict):
            assert span["metrics"]["_sampling_priority_v1"] == 1
            assert span["meta"]["appsec.events.payments.integration"] == "stripe"
            assert span["meta"]["appsec.events.payments.success.id"] == "cs_test_aaaaa"

            return True

        interfaces.library.validate_one_span(self.r, validator=validator)

    # def setup_payment_failure(self):
    #     self.r = weblog.post("/stripe/webhook", json={

    #     })

    # def test_payment_failure(self):
    #     def validator(span: dict):
    #         assert span["metrics"]["_sampling_priority_v1"] == 1
    #         assert span["meta"]["appsec.events.payments.integration"] == "stripe"
    #         assert span["meta"]["appsec.events.payments.failure.id"] == "cs_test_aaaaa"

    #         return True

    #     interfaces.library.validate_one_span(self.r, validator=validator)

    # def setup_payment_cancellation(self):
    #     self.r = weblog.post("/stripe/webhook", json={

    #     })

    # def test_payment_cancellation(self):
        def validator(span: dict):
            assert span["metrics"]["_sampling_priority_v1"] == 1
            assert span["meta"]["appsec.events.payments.integration"] == "stripe"
            assert span["meta"]["appsec.events.payments.cancellation.id"] == "cs_test_aaaaa"

            return True

        interfaces.library.validate_one_span(self.r, validator=validator)