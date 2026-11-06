# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2026 Datadog, Inc.

from urllib.parse import urlsplit

from utils import HttpResponse, features, interfaces, scenarios, weblog
from utils.dd_types import is_same_boolean
from tests.appsec.utils import find_series


def validate_event(request: HttpResponse, event_name: str, metadata: dict[str, str]) -> None:
    expected = {
        f"appsec.events.{event_name}.track": "true",
        f"_dd.appsec.events.{event_name}.sdk": "true",
        **{f"appsec.events.{event_name}.{key}": value for key, value in metadata.items()},
    }
    interfaces.library.validate_one_span(
        request,
        validator=lambda span: all(
            is_same_boolean(actual=span.get("meta", {}).get(key), expected=value) for key, value in expected.items()
        ),
    )


@features.custom_business_logic_events
@features.event_tracking_sdk_v2
@scenarios.appsec_lambda_default
class Test_Lambda_CustomEventV2:
    def setup_custom_event_v2(self):
        self.r = weblog.post(
            "/custom_event_v2",
            json={"event_name": "system_tests_event", "metadata": {"metadata0": "value0"}},
        )

    def test_custom_event_v2(self):
        assert self.r.status_code == 200
        validate_event(self.r, "system_tests_event", {"metadata0": "value0"})
        series = find_series("appsec", ["sdk.event"])
        # Telemetry covers the whole scenario, including the signup custom event.
        expected_count = sum(
            urlsplit(span.get("meta", {}).get("http.url", "")).path == "/custom_event_v2"
            for _, span in interfaces.library.get_root_spans()
        )
        actual_count = sum(
            point[1]
            for metric in series
            if metric.get("type") == "count"
            and "event_type:custom" in metric.get("tags", ())
            and "sdk_version:v2" in metric.get("tags", ())
            for point in metric["points"]
        )
        assert expected_count > 0, "No custom-event v2 requests found in traces"
        assert actual_count == expected_count, (actual_count, expected_count, series)


@features.user_monitoring
@scenarios.appsec_lambda_default
class Test_Lambda_UserSdk:
    def setup_user_sdk(self):
        self.r = weblog.get("/users", params={"user": "lambda_sdk_user"})

    def test_user_sdk(self):
        assert self.r.status_code == 200
        expected = {
            "usr.id": "lambda_sdk_user",
            "_dd.appsec.user.collection_mode": "sdk",
            **{f"usr.{key}": f"usr.{key}" for key in ("email", "name", "session_id", "role", "scope")},
        }
        interfaces.library.validate_one_span(
            self.r,
            validator=lambda span: all(span.get("meta", {}).get(key) == value for key, value in expected.items()),
        )


@features.user_monitoring
@features.custom_business_logic_events
@scenarios.appsec_lambda_default
class Test_Lambda_SignupSdk:
    """Java reports manual signup through a users.signup custom event; there is no signup SDK method."""

    def setup_signup_sdk_v1(self):
        self.r_v1 = weblog.get("/custom_event", params={"event_name": "users.signup"})

    def test_signup_sdk_v1(self):
        assert self.r_v1.status_code == 200
        validate_event(self.r_v1, "users.signup", {"metadata0": "value0", "metadata1": "value1"})

    def setup_signup_sdk_v2(self):
        self.r_v2 = weblog.post(
            "/custom_event_v2",
            json={
                "event_name": "users.signup",
                "metadata": {"usr.id": "signup_user", "usr.login": "signup_login"},
            },
        )

    def test_signup_sdk_v2(self):
        assert self.r_v2.status_code == 200
        validate_event(self.r_v2, "users.signup", {"usr.id": "signup_user", "usr.login": "signup_login"})
