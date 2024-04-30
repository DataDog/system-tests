# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
from utils import weblog, interfaces, features


@features.user_monitoring
class Test_UserLoginSuccessEvent:
    """Success test for User Login Event SDK for AppSec"""

    def setup_user_login_success_event(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        self.r = weblog.get("/user_login_success_event", headers=headers)

    def test_user_login_success_event(self):
        # Call the user login success SDK and validate tags

        def validate_user_login_success_tags(span):
            expected_tags = {
                "http.client_ip": "1.2.3.4",
                "usr.id": "system_tests_user",
                "appsec.events.users.login.success.track": "true",
                "appsec.events.users.login.success.metadata0": "value0",
                "appsec.events.users.login.success.metadata1": "value1",
            }

            for tag, expected_value in expected_tags.items():
                assert tag in span["meta"], f"Can't find {tag} in span's meta"
                value = span["meta"][tag]
                if value != expected_value:
                    raise Exception(f"{tag} value is '{value}', should be '{expected_value}'")

            return True

        interfaces.library.validate_spans(self.r, validate_user_login_success_tags)

    def setup_user_login_success_header_collection(self):
        headers = {
            "Accept":  "text/html",
            "Accept-Encoding": "br;q=1.0, gzip;q=0.8, *;q=0.1",
            "Accept-Language":  "en-GB, *;q=0.5",
            "Content-Language": "en-GB",
            "Content-Length": "0",
            "Content-Type": "text/html; charset=utf-8",
            "Content-Encoding": "deflate, gzip",
            "Host": "127.0.0.1:1234",
            "User-Agent": "Arachni/v1", #Benign User Agent 1.0",
            "X-Forwarded-For": "42.42.42.42, 43.43.43.43",
            "X-Client-IP": "42.42.42.42, 43.43.43.43",
            "X-Real-IP": "42.42.42.42, 43.43.43.43",
            "X-Forwarded": "42.42.42.42, 43.43.43.43",
            "X-Cluster-Client-IP": "42.42.42.42, 43.43.43.43",
            "Forwarded-For": "42.42.42.42, 43.43.43.43",
            "Forwarded": "42.42.42.42, 43.43.43.43",
            "Via": "42.42.42.42, 43.43.43.43",
            "True-Client-IP": "42.42.42.42, 43.43.43.43",
#             "CF-Connecting-IPv6": "::ffff:2a2a:2a2a",
            # "CF-Connecting-IP": "42.42.42.42",
            "Fastly-Client-IP": "42.42.42.42",
        }

        self.r = weblog.get("/user_login_success_event", headers=headers)

    def test_user_login_success_header_collection(self):
        # Call the user login success SDK and validate tags

        def validate_user_login_success_header_collection(span):
            expected_headers = ["Accept", "Accept-Encoding", "Accept-Language",
                "Content-Language", "Content-Length", "Content-Type",
                "Content-Encoding", "Host", "User-Agent", "X-Forwarded-For",
                "X-Client-IP", "X-Real-IP", "X-Forwarded", "X-Cluster-Client-IP",
                "Forwarded-For", "Forwarded", "Via", "True-Client-IP",
                "Fastly-Client-IP",
#                 "CF-Connecting-IPv6",
                # "CF-Connecting-IP",
            ]
            for header in expected_headers:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"
            return True

        interfaces.library.validate_spans(self.r, validate_user_login_success_header_collection)


@features.user_monitoring
class Test_UserLoginFailureEvent:
    """Failure test for User Login Event SDK for AppSec"""

    def setup_user_login_failure_event(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        self.r = weblog.get("/user_login_failure_event", headers=headers)

    def test_user_login_failure_event(self):
        # Call the user login failure SDK and validate tags

        def validate_user_login_failure_tags(span):
            expected_tags = {
                "http.client_ip": "1.2.3.4",
                "appsec.events.users.login.failure.usr.id": "system_tests_user",
                "appsec.events.users.login.failure.track": "true",
                "appsec.events.users.login.failure.usr.exists": "true",
                "appsec.events.users.login.failure.metadata0": "value0",
                "appsec.events.users.login.failure.metadata1": "value1",
            }

            for tag, expected_value in expected_tags.items():
                assert tag in span["meta"], f"Can't find {tag} in span's meta"
                value = span["meta"][tag]
                if value != expected_value:
                    raise Exception(f"{tag} value is '{value}', should be '{expected_value}'")

            return True

        interfaces.library.validate_spans(self.r, validate_user_login_failure_tags)

    def setup_user_login_failure_header_collection(self):
        headers = {
            "Accept":  "text/html",
            "Accept-Encoding": "br;q=1.0, gzip;q=0.8, *;q=0.1",
            "Accept-Language":  "en-GB, *;q=0.5",
            "Content-Language": "en-GB",
            "Content-Length": "0",
            "Content-Type": "text/html; charset=utf-8",
            "Content-Encoding": "deflate, gzip",
            "Host": "127.0.0.1:1234",
            "User-Agent": "Arachni/v1", #Benign User Agent 1.0",
            "X-Forwarded-For": "42.42.42.42, 43.43.43.43",
            "X-Client-IP": "42.42.42.42, 43.43.43.43",
            "X-Real-IP": "42.42.42.42, 43.43.43.43",
            "X-Forwarded": "42.42.42.42, 43.43.43.43",
            "X-Cluster-Client-IP": "42.42.42.42, 43.43.43.43",
            "Forwarded-For": "42.42.42.42, 43.43.43.43",
            "Forwarded": "42.42.42.42, 43.43.43.43",
            "Via": "42.42.42.42, 43.43.43.43",
            "True-Client-IP": "42.42.42.42, 43.43.43.43",
#             "CF-Connecting-IPv6": "::ffff:2a2a:2a2a",
            # "CF-Connecting-IP": "42.42.42.42",
            "Fastly-Client-IP": "42.42.42.42",
        }

        self.r = weblog.get("/user_login_failure_event", headers=headers)

    def test_user_login_failure_header_collection(self):
        # Call the user login failure SDK and validate tags

        def validate_user_login_failure_header_collection(span):
            expected_headers = ["Accept", "Accept-Encoding", "Accept-Language",
                "Content-Language", "Content-Length", "Content-Type",
                "Content-Encoding", "Host", "User-Agent", "X-Forwarded-For",
                "X-Client-IP", "X-Real-IP", "X-Forwarded", "X-Cluster-Client-IP",
                "Forwarded-For", "Forwarded", "Via", "True-Client-IP",
                "Fastly-Client-IP",
#                 "CF-Connecting-IPv6",
                # "CF-Connecting-IP",
            ]
            for header in expected_headers:
                assert f"http.request.headers.{header.lower()}" in span["meta"], f"Can't find {header} in span's meta"
            return True

        interfaces.library.validate_spans(self.r, validate_user_login_failure_header_collection)

@features.custom_business_logic_events
class Test_CustomEvent:
    """Test for Custom Event SDK for AppSec"""

    def setup_custom_event_event(self):
        headers = {
            "X-Forwarded-For": "1.2.3.4",
        }

        self.r = weblog.get("/custom_event", headers=headers)

    def test_custom_event_event(self):
        # Call the user login failure SDK and validate tags

        def validate_custom_event_tags(span):
            expected_tags = {
                "http.client_ip": "1.2.3.4",
                "appsec.events.system_tests_event.track": "true",
                "appsec.events.system_tests_event.metadata0": "value0",
                "appsec.events.system_tests_event.metadata1": "value1",
            }

            for tag, expected_value in expected_tags.items():
                assert tag in span["meta"], f"Can't find {tag} in span's meta"
                value = span["meta"][tag]
                if value != expected_value:
                    raise Exception(f"{tag} value is '{value}', should be '{expected_value}'")

            return True

        interfaces.library.validate_spans(self.r, validate_custom_event_tags)
