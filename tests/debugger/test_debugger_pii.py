# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from typing import Any

import tests.debugger.utils as debugger

from utils import context, features, scenarios, slow

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

DIRECT_SECRET = "DIRECT_SECRET_VALUE"
MAP_SECRET = "MAP_SECRET_VALUE"
EXCLUDED_IDENTIFIER_VALUE = "EXCLUDED_IDENTIFIER_VALUE"
NON_SENSITIVE_VALUE = "NON_SENSITIVE_VALUE"
REDACTED_MESSAGE_PLACEHOLDER = "{redacted}"
RAW_SECRETS = (DIRECT_SECRET, MAP_SECRET, "SHOULD_BE_REDACTED")


@features.debugger_pii_redaction
class BaseDebuggerPIIRedactionTest(debugger.BaseDebuggerTest):
    ############ setup ############
    _max_retries = 3
    _timeout_first = 5
    _timeout_next = 60

    def _pii_line(self) -> str:
        lines = self.method_and_language_to_line_number("Pii", self.get_tracer()["language"])
        if not lines:
            # Placeholder for manifest-disabled languages without a PII line-probe workload.
            return "0"
        return str(lines[0])

    def _assert_pii_line_mapping(self) -> None:
        lines = self.method_and_language_to_line_number("Pii", self.get_tracer()["language"])
        assert len(lines) == 1, f"Expected one PII probe line, got {lines!r}"

    def _setup(self, *, line_probe: bool = False):
        self.initialize_weblog_remote_config()

        if line_probe:
            probes = debugger.read_probes("pii_line")
            for probe in probes:
                probe["where"]["lines"] = [self._pii_line()]
        else:
            probes = debugger.read_probes("pii")

        self.set_probes(probes)
        self.send_rc_probes()
        self.wait_for_all_probes(statuses=["INSTALLED"])

        retries = 0
        timeout = self._timeout_first
        snapshot_found = False

        while not snapshot_found and retries < self._max_retries:
            self.send_weblog_request("/debugger/pii", reset=(retries == 0))
            snapshot_found = self.wait_for_all_snapshots(timeout=timeout)
            timeout = self._timeout_next
            retries += 1

        if not snapshot_found:
            self.setup_failures.append("Snapshot was not received")
        else:
            # The EMITTING diagnostic can arrive after the snapshot itself
            # (notably on .NET where it is reported asynchronously), so wait
            # for it explicitly before the assertion runs.
            self.wait_for_all_probes(statuses=["EMITTING"])

    ############ assert ############
    def _assert(self, excluded_identifiers: list[str] | None = None, *, line_probe: bool = False):
        if line_probe:
            self._assert_pii_line_mapping()
        self.collect()
        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self.assert_all_probes_are_emitting()
        self.assert_all_weblog_responses_ok()

        self._validate_pii_keyword_redaction(excluded_identifiers, line_probe=line_probe)
        if context.library != "nodejs":  # Node.js does not support type redacting
            self._validate_pii_type_redaction(line_probe=line_probe)

    def _validate_pii_keyword_redaction(self, excluded_identifiers: list[str] | None, *, line_probe: bool):
        not_redacted = []
        not_found = list(set(REDACTED_KEYS))
        improperly_redacted = []
        excluded_identifiers = excluded_identifiers if excluded_identifiers else []

        for probe_id in self.probe_ids:
            if probe_id not in self.probe_snapshots:
                raise KeyError(
                    f"Probe id {probe_id!r} not found in probe_snapshots. "
                    f"Snapshot keys received: {list(self.probe_snapshots.keys())!r}. "
                    "Snapshots may be in multipart format that was not unwrapped, or the tracer may echo a different probe id."
                )
            base = self.probe_snapshots[probe_id][0]
            snapshot = base.get("debugger", {}).get("snapshot") or base["debugger.snapshot"]

            if line_probe:
                fields = snapshot["captures"]["lines"][self._pii_line()]["locals"]["pii"]["fields"]
            else:
                fields = snapshot["captures"]["return"]["locals"]["pii"]["fields"]

            # Check if fields that should be redacted are properly redacted
            for field_name in set(REDACTED_KEYS):
                if context.library == "ruby":
                    check_field_name = "@" + field_name
                else:
                    check_field_name = field_name

                if check_field_name in fields:
                    not_found.remove(field_name)

                    # Fields not included in excluded_identifiers should not have values
                    if "value" in fields[check_field_name] and field_name not in excluded_identifiers:
                        not_redacted.append(field_name)

                    # Fields included in excluded_identifiers should have values
                    if "value" not in fields[check_field_name] and field_name in excluded_identifiers:
                        improperly_redacted.append(field_name)

        error_message = []
        if not_redacted:
            not_redacted.sort()
            error_message.append("Fields not properly redacted: " + "".join([f"{item}, " for item in not_redacted]))

        if not_found:
            not_found.sort()
            error_message.append("Fields not found: " + "".join([f"{item}, " for item in not_found]))

        if improperly_redacted:
            improperly_redacted.sort()
            error_message.append(
                "Excluded fields improperly redacted: " + "".join([f"{item}, " for item in improperly_redacted])
            )

        if error_message:
            raise ValueError(". ".join(error_message))

    def _validate_pii_type_redaction(self, *, line_probe: bool):
        not_redacted = []

        for probe_id in self.probe_ids:
            if probe_id not in self.probe_snapshots:
                raise KeyError(
                    f"Probe id {probe_id!r} not found in probe_snapshots. "
                    f"Snapshot keys received: {list(self.probe_snapshots.keys())!r}."
                )
            base = self.probe_snapshots[probe_id][0]
            snapshot = base.get("debugger", {}).get("snapshot") or base["debugger.snapshot"]

            for type_name in REDACTED_TYPES:
                if line_probe:
                    type_info = snapshot["captures"]["lines"][self._pii_line()]["locals"][type_name]
                else:
                    type_info = snapshot["captures"]["return"]["locals"][type_name]

                if "fields" in type_info:
                    not_redacted.append(type_name)

        error_message = ""
        if not_redacted:
            not_redacted.sort()
            error_message += "Types not properly redacted: " + "".join([f"{item}, " for item in not_redacted])

        if error_message != "":
            raise ValueError(error_message)

    def _create_log_message_probe(self, label: str, expression: dict[str, Any]) -> dict[str, Any]:
        probe: dict[str, Any] = debugger.read_probes("expression_probe_base")[0]
        probe["id"] = debugger.generate_probe_id("log")
        probe["where"] = {
            "typeName": None,
            "sourceFile": "ACTUAL_SOURCE_FILE",
            "lines": [self._pii_line()],
        }
        probe["segments"] = [
            {"str": f"{label}="},
            {"dsl": "", "json": expression},
        ]
        return probe

    def _setup_log_probe_messages(
        self,
        redacted_expressions: dict[str, dict[str, Any]],
        visible_expressions: dict[str, tuple[dict[str, Any], str]] | None = None,
        *,
        require_exact_redaction: bool = True,
        required_redacted_message_values: tuple[str, ...] = (),
    ) -> None:
        self.initialize_weblog_remote_config()
        visible_expressions = visible_expressions or {}

        probes: list[dict[str, Any]] = []
        self.redacted_log_message_probe_ids: set[str] = set()
        self.exact_redacted_log_message_values: dict[str, str] = {}
        self.redacted_log_message_required_values: dict[str, tuple[str, ...]] = {}
        self.visible_log_message_values: dict[str, str] = {}

        for label, expression in redacted_expressions.items():
            probe = self._create_log_message_probe(label, expression)
            probes.append(probe)
            self.redacted_log_message_probe_ids.add(probe["id"])
            if require_exact_redaction:
                self.exact_redacted_log_message_values[probe["id"]] = f"{label}={REDACTED_MESSAGE_PLACEHOLDER}"
            if required_redacted_message_values:
                self.redacted_log_message_required_values[probe["id"]] = required_redacted_message_values

        for label, (expression, expected_value) in visible_expressions.items():
            probe = self._create_log_message_probe(label, expression)
            probes.append(probe)
            self.visible_log_message_values[probe["id"]] = expected_value

        self.set_probes(probes)
        self.send_rc_probes()
        if not self.wait_for_all_probes(statuses=["INSTALLED"]):
            self.setup_failures.append("Log probes did not reach INSTALLED status")
            return

        retries = 0
        timeout = self._timeout_first
        snapshots_found = False
        while not snapshots_found and retries < self._max_retries:
            self.send_weblog_request("/debugger/pii", reset=(retries == 0))
            snapshots_found = self.wait_for_all_snapshots(timeout=timeout)
            timeout = self._timeout_next
            retries += 1

        if not snapshots_found:
            self.setup_failures.append("Rendered log-probe messages were not received")
        else:
            self.wait_for_all_probes(statuses=["EMITTING"])

    def _validate_log_probe_message_redaction(self) -> None:
        messages: dict[str, list[str]] = {}
        for probe_id in self.probe_ids:
            snapshots = self.probe_snapshots.get(probe_id, [])
            for snapshot in snapshots:
                message = snapshot.get("message")
                if isinstance(message, str):
                    messages.setdefault(probe_id, []).append(message)

        missing_probe_ids = set(self.probe_ids) - messages.keys()
        assert not missing_probe_ids, f"Rendered messages were not received for probes: {sorted(missing_probe_ids)}"

        for probe_id in self.redacted_log_message_probe_ids:
            for message in messages[probe_id]:
                expected_message = self.exact_redacted_log_message_values.get(probe_id)
                if expected_message is not None:
                    assert message == expected_message, (
                        f"Expected rendered message {expected_message!r} for probe {probe_id}, got {message!r}"
                    )
                else:
                    assert REDACTED_MESSAGE_PLACEHOLDER in message, (
                        f"Expected {REDACTED_MESSAGE_PLACEHOLDER!r} in rendered message for probe {probe_id}, "
                        f"got {message!r}"
                    )
                for required_value in self.redacted_log_message_required_values.get(probe_id, ()):
                    assert required_value in message, (
                        f"Expected visible value {required_value!r} in rendered message for probe {probe_id}, "
                        f"got {message!r}"
                    )

        for probe_id, expected_value in self.visible_log_message_values.items():
            for message in messages[probe_id]:
                assert expected_value in message, (
                    f"Expected visible value {expected_value!r} in rendered message for probe {probe_id}, "
                    f"got {message!r}"
                )

        rendered_messages = "\n".join(message for probe_messages in messages.values() for message in probe_messages)
        for secret in RAW_SECRETS:
            assert secret not in rendered_messages, f"Raw secret {secret!r} leaked in rendered log-probe messages"

    def _assert_log_probe_messages(self) -> None:
        self._assert_pii_line_mapping()
        self.collect()
        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        self.assert_all_probes_are_emitting()
        self.assert_all_weblog_responses_ok()
        self._validate_log_probe_message_redaction()


@scenarios.debugger_pii_redaction
class Test_Debugger_PII_Redaction(BaseDebuggerPIIRedactionTest):
    ############ test ############
    ### method ###
    def setup_pii_redaction_method_full(self):
        self._setup()

    @slow
    def test_pii_redaction_method_full(self):
        self._assert()

    ### line ###
    def setup_pii_redaction_line_full(self):
        self._setup(line_probe=True)

    def test_pii_redaction_line_full(self):
        self._assert(line_probe=True)


@scenarios.tracing_config_nondefault_4
class Test_Debugger_PII_Redaction_Excluded_Identifiers(BaseDebuggerPIIRedactionTest):
    ### excluded identifiers ###
    def setup_pii_redaction_excluded_identifiers(self):
        self._setup(line_probe=True)

    def test_pii_redaction_excluded_identifiers(self):
        excluded_identifiers = ["_2fa", "cookie", "sessionid"]
        self._assert(excluded_identifiers, line_probe=True)

    def setup_pii_redaction_log_probe_identifiers(self) -> None:
        self._setup_log_probe_messages(
            redacted_expressions={
                "direct": {"ref": "password"},
                "member": {"getmember": [{"ref": "pii"}, "password"]},
            },
            visible_expressions={
                "excluded_identifier": (
                    {"index": [{"ref": "user"}, "_2fa"]},
                    EXCLUDED_IDENTIFIER_VALUE,
                ),
                "non_sensitive": (
                    {"index": [{"ref": "user"}, "name"]},
                    NON_SENSITIVE_VALUE,
                ),
            },
        )

    @slow
    def test_pii_redaction_log_probe_identifiers(self) -> None:
        self._assert_log_probe_messages()

    def setup_pii_redaction_log_probe_map_rendering(self) -> None:
        self._setup_log_probe_messages(
            redacted_expressions={"map": {"ref": "user"}},
            require_exact_redaction=False,
            required_redacted_message_values=(EXCLUDED_IDENTIFIER_VALUE, NON_SENSITIVE_VALUE),
        )

    @slow
    def test_pii_redaction_log_probe_map_rendering(self) -> None:
        self._assert_log_probe_messages()

    def setup_pii_redaction_log_probe_map_key(self) -> None:
        self._setup_log_probe_messages(redacted_expressions={"literal_key": {"index": [{"ref": "user"}, "password"]}})

    @slow
    def test_pii_redaction_log_probe_map_key(self) -> None:
        self._assert_log_probe_messages()

    def setup_pii_redaction_log_probe_computed_key(self) -> None:
        self._setup_log_probe_messages(
            redacted_expressions={
                "computed_key": {
                    "index": [
                        {"ref": "user"},
                        {"substring": ["xpasswordx", 1, 9]},
                    ]
                }
            }
        )

    @slow
    def test_pii_redaction_log_probe_computed_key(self) -> None:
        self._assert_log_probe_messages()

    def setup_pii_redaction_log_probe_sensitive_type(self) -> None:
        self._setup_log_probe_messages(redacted_expressions={"sensitive_type": {"ref": "customPii"}})

    @slow
    def test_pii_redaction_log_probe_sensitive_type(self) -> None:
        self._assert_log_probe_messages()
