# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as base

from utils import (
    scenarios,
    interfaces,
    weblog,
    features,
    bug,
    missing_feature,
    irrelevant,
    context,
    remote_config as rc,
)

REDACTED_KEYS = [
    "_2fa",
    "accesstoken",
    "access_token",
    "Access_Token",
    "accessToken",
    "AccessToken",
    "ACCESSTOKEN",
    "aiohttpsession",
    "apikey",
    "apisecret",
    "apisignature",
    "applicationkey",
    "auth",
    "authorization",
    "authtoken",
    "ccnumber",
    "certificatepin",
    "cipher",
    "clientid",
    "clientsecret",
    "connectionstring",
    "connectsid",
    "cookie",
    "credentials",
    "creditcard",
    "csrf",
    "csrftoken",
    "cvv",
    "databaseurl",
    "dburl",
    "encryptionkey",
    "encryptionkeyid",
    "env",
    "geolocation",
    "gpgkey",
    "ipaddress",
    "jti",
    "jwt",
    "licensekey",
    "masterkey",
    "mysqlpwd",
    "nonce",
    "oauth",
    "oauthtoken",
    "otp",
    "passhash",
    "passwd",
    "password",
    "passwordb",
    "pemfile",
    "pgpkey",
    "phpsessid",
    "pin",
    "pincode",
    "pkcs8",
    "privatekey",
    "publickey",
    "pwd",
    "recaptchakey",
    "refreshtoken",
    "routingnumber",
    "salt",
    "secret",
    "secretkey",
    "secrettoken",
    "securityanswer",
    "securitycode",
    "securityquestion",
    "serviceaccountcredentials",
    "session",
    "sessionid",
    "sessionkey",
    "setcookie",
    "signature",
    "signaturekey",
    "sshkey",
    "ssn",
    "symfony",
    "token",
    "transactionid",
    "twiliotoken",
    "usersession",
    "voterid",
    "xapikey",
    "xauthtoken",
    "xcsrftoken",
    "xforwardedfor",
    "xrealip",
    "xsrf",
    "xsrftoken",
    "customidentifier1",
    "customidentifier2",
]

REDACTED_TYPES = ["customPii"]


def filter(keys_to_filter):
    return [item for item in REDACTED_KEYS if item not in keys_to_filter]


@features.debugger_pii_redaction
@scenarios.debugger_pii_redaction
class Test_Debugger_PII_Redaction(base._Base_Debugger_Test):
    def _setup(self, probes_file):
        probes = base.read_probes(probes_file)
        self.expected_probe_ids = base.extract_probe_ids(probes)
        self.rc_state = rc.send_debugger_command(probes, version=1)

        interfaces.agent.wait_for(self.wait_for_all_probes_installed, timeout=30)

        self.weblog_responses = [weblog.get("/debugger/pii")]

    def _test(self, redacted_keys, redacted_types, line_probe=False):
        self.assert_all_states_not_error()
        self.assert_all_probes_are_installed()
        self.assert_all_weblog_responses_ok()

        self._validate_pii_keyword_redaction(redacted_keys, line_probe=line_probe)
        self._validate_pii_type_redaction(redacted_types, line_probe=line_probe)

    def setup_pii_redaction_full(self):
        self._setup("pii")

    @missing_feature(context.library < "java@1.34", reason="keywords are not fully redacted")
    @missing_feature(context.library < "dotnet@2.51", reason="keywords are not fully redacted")
    @bug(context.library == "python@2.16.0", reason="DEBUG-3127")
    @bug(context.library == "python@2.16.1", reason="DEBUG-3127")
    # Ruby requires @irrelevant rather than @missing_feature to skip setup
    # for this test (which will interfere with the line probe test).
    @irrelevant(context.library == "ruby", reason="Local variable capture not implemented for method probes")
    def test_pii_redaction_full(self):
        self._test(REDACTED_KEYS, REDACTED_TYPES)

    def setup_pii_redaction_java_1_33(self):
        self._setup("pii")

    @irrelevant(context.library != "java@1.33", reason="not relevant for other version")
    def test_pii_redaction_java_1_33(self):
        self._test(
            filter(
                [
                    "address",
                    "connectionstring",
                    "connectsid",
                    "geolocation",
                    "ipaddress",
                    "oauthtoken",
                    "secretkey",
                    "xsrf",
                ]
            ),
            REDACTED_TYPES,
        )

    def setup_pii_redaction_dotnet_2_50(self):
        self._setup("pii")

    @irrelevant(context.library != "dotnet@2.50", reason="not relevant for other version")
    @bug(
        context.weblog_variant == "uds" and context.library == "dotnet@2.50.0", reason="APMRP-360",
    )  # bug with UDS protocol on this version
    def test_pii_redaction_dotnet_2_50(self):
        self._test(filter(["applicationkey", "connectionstring"]), REDACTED_TYPES)

    def setup_pii_redaction_line(self):
        self._setup("pii_line")

    @irrelevant(context.library != "ruby", reason="Ruby needs to use line probes to capture variables")
    def test_pii_redaction_line(self):
        self._test(REDACTED_KEYS, REDACTED_TYPES, True)

    def _validate_pii_keyword_redaction(self, should_redact_field_names, line_probe=False):
        agent_logs_endpoint_requests = list(interfaces.agent.get_data(path_filters="/api/v2/logs"))
        not_redacted = []
        not_found = list(set(should_redact_field_names))

        for request in agent_logs_endpoint_requests:
            content = request["request"]["content"]

            if content:
                for item in content:
                    snapshot = item.get("debugger", {}).get("snapshot") or item.get("debugger.snapshot")

                    if snapshot:
                        for field_name in should_redact_field_names:
                            if line_probe:
                                fields = snapshot["captures"]["lines"]["33"]["locals"]["pii"]["fields"]
                            else:
                                fields = snapshot["captures"]["return"]["locals"]["pii"]["fields"]

                            # Ruby prefixes instance variable names with @
                            if context.library == "ruby":
                                check_field_name = "@" + field_name
                            else:
                                check_field_name = field_name

                            if check_field_name in fields:
                                not_found.remove(field_name)

                                if "value" in fields[check_field_name]:
                                    not_redacted.append(field_name)
        error_message = ""
        if not_redacted:
            not_redacted.sort()
            error_message = "Fields not properly redacted: " + "".join([f"{item}, " for item in not_redacted])

        if not_found:
            not_found.sort()
            error_message += ". Fields not found: " + "".join([f"{item}, " for item in not_found])

        if error_message != "":
            raise ValueError(error_message)

    def _validate_pii_type_redaction(self, should_redact_types, line_probe=False):
        agent_logs_endpoint_requests = list(interfaces.agent.get_data(path_filters="/api/v2/logs"))
        not_redacted = []

        for request in agent_logs_endpoint_requests:
            content = request["request"]["content"]

            if content:
                for item in content:
                    snapshot = item.get("debugger", {}).get("snapshot") or item.get("debugger.snapshot")

                    if snapshot:
                        for type_name in should_redact_types:
                            if line_probe:
                                type_info = snapshot["captures"]["lines"]["33"]["locals"][type_name]
                            else:
                                type_info = snapshot["captures"]["return"]["locals"][type_name]

                            if "fields" in type_info:
                                not_redacted.append(type_name)

        error_message = ""
        if not_redacted:
            not_redacted.sort()
            error_message = "Types not properly redacted: " + "".join([f"{item}, " for item in not_redacted])

        if error_message != "":
            raise ValueError(error_message)
