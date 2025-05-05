# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as debugger

from utils import (
    scenarios,
    features,
    bug,
    missing_feature,
    context,
)

REDACTED_KEYS = [
    "_2fa",
    "ACCESSTOKEN",
    "Access_Token",
    "AccessToken",
    "accessToken",
    "access_token",
    "accesstoken",
    "aiohttpsession",
    "apikey",
    "apisecret",
    "apisignature",
    "appkey",
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


@features.debugger_pii_redaction
@scenarios.debugger_pii_redaction
class Test_Debugger_PII_Redaction(debugger.BaseDebuggerTest):
    ############ setup ############
    def _setup(self, *, line_probe=False):
        self.initialize_weblog_remote_config()

        if line_probe:
            probes = debugger.read_probes("pii_line")
        else:
            probes = debugger.read_probes("pii")

        self.set_probes(probes)
        self.send_rc_probes()
        self.wait_for_all_probes(statuses=["INSTALLED"])
        self.send_weblog_request("/debugger/pii")
        self.wait_for_all_probes(statuses=["EMITTING"])

    ############ assert ############
    def _assert(self, redacted_keys, redacted_types, *, line_probe=False):
        self.collect()
        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self.assert_all_probes_are_emitting()
        self.assert_all_weblog_responses_ok()

        self._validate_pii_keyword_redaction(redacted_keys, line_probe)
        if context.library != "nodejs":  # Node.js does not support type redacting
            self._validate_pii_type_redaction(redacted_types, line_probe)

    def _validate_pii_keyword_redaction(self, should_redact_field_names, line_probe):
        not_redacted = []
        not_found = list(set(should_redact_field_names))

        for probe_id in self.probe_ids:
            base = self.probe_snapshots[probe_id][0]
            snapshot = base.get("debugger", {}).get("snapshot") or base["debugger.snapshot"]

            for field_name in should_redact_field_names:
                if line_probe:
                    fields = snapshot["captures"]["lines"]["64"]["locals"]["pii"]["fields"]
                else:
                    fields = snapshot["captures"]["return"]["locals"]["pii"]["fields"]

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

    def _validate_pii_type_redaction(self, should_redact_types, line_probe):
        not_redacted = []

        for probe_id in self.probe_ids:
            base = self.probe_snapshots[probe_id][0]
            snapshot = base.get("debugger", {}).get("snapshot") or base["debugger.snapshot"]

            for type_name in should_redact_types:
                if line_probe:
                    type_info = snapshot["captures"]["lines"]["64"]["locals"][type_name]
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

    ############ test ############
    ### method ###
    def setup_pii_redaction_method_full(self):
        self._setup()

    @missing_feature(context.library < "java@1.34", reason="keywords are not fully redacted", force_skip=True)
    @missing_feature(context.library < "dotnet@2.51", reason="keywords are not fully redacted", force_skip=True)
    @bug(context.library == "python@2.16.0", reason="DEBUG-3127")
    @bug(context.library == "python@2.16.1", reason="DEBUG-3127")
    @missing_feature(
        context.library == "ruby", reason="Local variable capture not implemented for method probes", force_skip=True
    )
    @missing_feature(context.library == "nodejs", reason="Not yet implemented", force_skip=True)
    def test_pii_redaction_method_full(self):
        self._assert(REDACTED_KEYS, REDACTED_TYPES)

    ### line ###
    def setup_pii_redaction_line_full(self):
        self._setup(line_probe=True)

    def test_pii_redaction_line_full(self):
        self._assert(REDACTED_KEYS, REDACTED_TYPES, line_probe=True)
