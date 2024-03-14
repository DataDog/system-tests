# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import scenarios, interfaces, weblog, features, missing_feature, context
from utils.tools import logger
import test_debugger_base as base

def validate_pii_redaction(should_redact_field_names):
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
    error_message = ''
    if not_redacted:
        not_redacted.sort()
        error_message = "Fields not properly redacted: " + ''.join([f"{item}, " for item in not_redacted])

    if not_found:
        not_found.sort()
        error_message += ". Fields not found: " + ''.join([f"{item}, " for item in not_found])

    if error_message != '':
        raise ValueError(error_message)

@features.debugger_pii_redaction
@scenarios.debugger_pii_redaction
class Test_Debugger_PII_Redaction(base._Base_Debugger_Snapshot_Test):
    pii_responses = []

    def setup_mix_probe(self):
        self.expected_probe_ids = [
            "log170aa-acda-4453-9111-1478a6method",
        ]

        interfaces.library.wait_for_remote_config_request()
        interfaces.agent.wait_for(self.wait_for_all_probes_installed, timeout=30)

        self.pii_responses.append(weblog.get("/debugger/log/pii/1"))
        self.pii_responses.append(weblog.get("/debugger/log/pii/2"))
        self.pii_responses.append(weblog.get("/debugger/log/pii/3"))
        self.pii_responses.append(weblog.get("/debugger/log/pii/4"))
        self.pii_responses.append(weblog.get("/debugger/log/pii/5"))
        self.pii_responses.append(weblog.get("/debugger/log/pii/6"))

    @missing_feature(context.library >= "java@1.27", reason="introduction of new EMITTING probe status")
    def test_mix_probe(self):
        self.assert_remote_config_is_sent()
        self.assert_all_probes_are_installed()

        for respone in self.pii_responses:
            assert respone.status_code == 200

        expected_probes = {
            "log170aa-acda-4453-9111-1478a6method": "INSTALLED",
        }

        expected_snapshots = [
            "log170aa-acda-4453-9111-1478a6method",
        ]

        base.validate_probes(expected_probes)
        base.validate_snapshots(expected_snapshots)

        redacted_names = [
            # commented fields are not redacted yet
            # "accesstoken",
            "address",
            # "aiohttpsession",
            "apikey",
            # "apisecret",
            # "apisignature",
            "auth",
            "authorization",
            # "authtoken",
            # "bankaccountnumber",
            "birthdate",
            # "ccnumber",
            # "certificatepin",
            "cipher",
            # "clientid",
            # "clientsecret",
            "config",
            # "connectsid",
            "cookie",
            "credentials",
            "creditcard",
            "csrf",
            "csrftoken",
            "cvv",
            # "databaseurl",
            # "dburl",
            # "driverlicense",
            "email",
            # "encryptionkey",
            # "encryptionkeyid",
            "env",
            # "geolocation",
            "gpgkey",
            # "ipaddress",
            "jti",
            "jwt",
            # "licensekey",
            "licenseplate",
            "maidenname",
            "mailaddress",
            # "masterkey",
            # "mysqlpwd",
            "nonce",
            "oauth",
            # "oauthtoken",
            "otp",
            "passhash",
            "passport",
            "passportno",
            "passportnum",
            # "passportnumber",
            "passwd",
            "password",
            "passwordb",
            # "pemfile",
            "pgpkey",
            "phone",
            "phoneno",
            "phonenum",
            "phonenumber",
            # "phpsessid",
            "pin",
            "pincode",
            "pkcs8",
            "plateno",
            "platenum",
            "platenumber",
            "privatekey",
            "province",
            # "publickey",
            "pwd",
            # "recaptchakey",
            # "refreshtoken",
            # "remoteaddr",
            # "routingnumber",
            "salt",
            "secret",
            # "secretkey",
            # "secrettoken",
            # "securityanswer",
            # "securitycode",
            # "securityquestion",
            # "serviceaccountcredentials",
            "session",
            "sessionid",
            # "sessionkey",
            # "setcookie",
            "signature",
            # "signaturekey",
            "sshkey",
            "ssn",
            "symfony",
            # "taxidentificationnumber",
            "telephone",
            "token",
            # "transactionid",
            # "twiliotoken",
            # "usersession",
            # "voterid",
            # "xapikey",
            # "xauthtoken",
            # "xcsrftoken",
            # "xforwardedfor",
            # "xrealip",
            "zipcode",
            # "xsrf",
            # "xsrftoken",
        ]

        validate_pii_redaction(redacted_names)