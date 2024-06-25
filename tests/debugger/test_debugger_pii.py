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

PROBES = [
    {
        "language": "",
        "id": "log170aa-acda-4453-9111-1478a6method",
        "where": {"typeName": "ACTUAL_TYPE_NAME", "methodName": "Pii", "sourceFile": None},
        "evaluateAt": "EXIT",
        "captureSnapshot": True,
        "capture": {"maxFieldCount": 200},
    }
]


def filter(keys_to_filter):
    return [item for item in REDACTED_KEYS if item not in keys_to_filter]


@features.debugger_pii_redaction
@scenarios.debugger_pii_redaction
class Test_Debugger_PII_Redaction(base._Base_Debugger_Test):
    probes_state = None

    def _setup(self):

        self.expected_probe_ids = [
            "log170aa-acda-4453-9111-1478a6method",
        ]

        # trick to avoid to re-run the setup function for each test: we save the result of weblog_responses/probes_state
        # in class rather than class instance (each test got it's own class instance)
        # and if it exists, we pick it from there
        if Test_Debugger_PII_Redaction.probes_state is None:
            # setup has not been run yet
            rc.send_command(
                raw_payload=rc.build_debugger_command(probes=None, version=0), wait_for_acknowledged_status=False
            )
            payload = rc.build_debugger_command(probes=PROBES, version=1)

            Test_Debugger_PII_Redaction.probes_state = rc.send_command(
                raw_payload=payload, wait_for_acknowledged_status=False
            )
            interfaces.agent.wait_for(self.wait_for_all_probes_installed, timeout=30)

            Test_Debugger_PII_Redaction.weblog_responses = [weblog.get("/debugger/pii")]

        # get values from class
        self.weblog_responses = Test_Debugger_PII_Redaction.weblog_responses
        self.probes_state = Test_Debugger_PII_Redaction.probes_state

    def _test(self, redacted_keys, redacted_types):
        # apply_state is not ACKNOWLEDGED, but UNACKNOWLEDGED
        # assert self.probes_state is not None and self.probes_state["apply_state"] == rc.ApplyState.ACKNOWLEDGED
        self.assert_remote_config_is_sent()
        self.assert_all_probes_are_installed()
        self.assert_all_weblog_responses_ok()

        base.validate_probes(
            {"log170aa-acda-4453-9111-1478a6method": "INSTALLED",}
        )

        base.validate_snapshots(
            ["log170aa-acda-4453-9111-1478a6method",]
        )

        self._validate_pii_keyword_redaction(redacted_keys)
        self._validate_pii_type_redaction(redacted_types)

    def _validate_pii_keyword_redaction(self, should_redact_field_names):
        agent_logs_endpoint_requests = list(interfaces.agent.get_data(path_filters="/api/v2/logs"))
        not_redacted = []
        not_found = list(set(should_redact_field_names))

        for request in agent_logs_endpoint_requests:
            content = request["request"]["content"]

            if content is not None:
                for content in content:
                    debugger = content["debugger"]

                    if "snapshot" in debugger:
                        for field_name in should_redact_field_names:
                            fields = debugger["snapshot"]["captures"]["return"]["locals"]["pii"]["fields"]

                            if field_name in fields:
                                not_found.remove(field_name)

                                if "value" in fields[field_name]:
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

    def _validate_pii_type_redaction(self, should_redact_types):
        agent_logs_endpoint_requests = list(interfaces.agent.get_data(path_filters="/api/v2/logs"))
        not_redacted = []

        for request in agent_logs_endpoint_requests:
            content = request["request"]["content"]

            if content is not None:
                for content in content:
                    debugger = content["debugger"]

                    if "snapshot" in debugger:
                        for type_name in should_redact_types:
                            type_info = debugger["snapshot"]["captures"]["return"]["locals"][type_name]

                            if "fields" in type_info:
                                not_redacted.append(type_name)

        error_message = ""
        if not_redacted:
            not_redacted.sort()
            error_message = "Types not properly redacted: " + "".join([f"{item}, " for item in not_redacted])

        if error_message != "":
            raise ValueError(error_message)

    def setup_pii_redaction_full(self):
        self._setup()

    @missing_feature(context.library < "java@1.34", reason="keywords are not fully redacted")
    @missing_feature(context.library < "dotnet@2.51", reason="keywords are not fully redacted")
    def test_pii_redaction_full(self):
        self._test(REDACTED_KEYS, REDACTED_TYPES)

    def setup_pii_redaction_java_1_33(self):
        self._setup()

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
        self._setup()

    @irrelevant(context.library != "dotnet@2.50", reason="not relevant for other version")
    @bug(
        weblog_variant="uds" and context.library == "dotnet@2.50.0", reason="bug with UDS protocol on this version",
    )
    def test_pii_redaction_dotnet_2_50(self):
        self._test(filter(["applicationkey", "connectionstring"]), REDACTED_TYPES)
