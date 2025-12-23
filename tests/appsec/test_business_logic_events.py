from utils import scenarios
from utils import weblog
from utils import interfaces


@scenarios.stripe
class Test_Business_Logic_Events_Stripe:
    def setup_checkout_session(self):
        self.r = weblog.post("/stripe/create_checkout_session")

    def test_checkout_session(self):
        def validator(span: dict):
            assert span["metrics"]["_sampling_priority_v1"] == 1
            assert span["meta"]["appsec.events.payments.integration"] == "stripe"
            assert span["meta"]["appsec.events.payments.creation.id"].startswith("cs_test_Pv")
            # assert span["metrics"]["appsec.events.payments.creation.amount_total"] == 406046392
            assert span["meta"]["appsec.events.payments.creation.client_reference_id"] == "superdiaz"
            # assert span["meta"]["appsec.events.payments.creation.currency"] == "topkek@topkek.com"
            assert span["meta"]["appsec.events.payments.creation.customer_email"] == "topkek@topkek.com"
            # appsec.events.payments.creation.discounts.coupon
            # appsec.events.payments.creation.discounts.promotion_code
            assert span["metrics"]["appsec.events.payments.creation.livemode"] == 0
            # assert span["metrics"]["appsec.events.payments.creation.total_details.amount_discount"] == 406046392
            # assert span["metrics"]["appsec.events.payments.creation.total_details.amount_shipping"] == 406046392

            return True

        interfaces.library.validate_one_span(self.r, validator=validator)


# paymentIntent
# appsec.events.payments.creation.amount
# appsec.events.payments.creation.payment_method
# appsec.events.payments.creation.receipt_email