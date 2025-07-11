# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""AppSec validators"""

from collections import Counter
from collections.abc import Callable
from utils.interfaces._library.appsec_data import rule_id_to_type
from utils._logger import logger


class _WafAttack:
    def __init__(
        self,
        rule: str | type | None = None,
        pattern: str | None = None,
        patterns: list[str] | None = None,
        value: str | None = None,
        address: str | None = None,
        key_path: str | list[str] | None = None,
        span_validator: Callable | None = None,
    ):
        # rule can be a rule id, or a rule type
        if rule is None:
            self.rule_id = None
            self.rule_type = None

        elif isinstance(rule, str):
            self.rule_id = rule
            self.rule_type = None

        else:
            self.rule_id = None
            self.rule_type = rule.__name__

        self.pattern = pattern
        self.patterns = patterns
        self.value = value

        self.address = address
        self.key_path = key_path

        self.span_validator = span_validator

    @staticmethod
    def _get_parameters(event: dict) -> list:
        result = []

        for parameter in event.get("rule_match", {}).get("parameters", []):
            if "address" in parameter:  # 1.0.0
                address = parameter["address"]

            elif "name" in parameter:  # 0.1.0
                parts = parameter["name"].split(":", 1)
                address = parts[0]

            else:
                continue

            key_path = parameter.get("key_path", [])

            # depending on the lang/framework, the last element may be an array, or not
            # So, a tailing 0 is added to the key path
            if key_path and key_path[-1] in (0, "0"):
                key_path = key_path[:-1]

            result.append((address, key_path))

        return result

    def validate(self, span: dict, appsec_data: dict):
        if "triggers" not in appsec_data:
            logger.error("triggers is not in appsec_data")

        for trigger in appsec_data["triggers"]:
            patterns = []
            values = []
            addresses = []
            full_addresses = []
            rule_id = trigger.get("rule", {}).get("id")
            rule_type = trigger.get("rule", {}).get("tags", {}).get("type")

            # Some agent does not report rule type ??
            if not rule_type:
                rule_type = rule_id_to_type.get(rule_id)

            for match in trigger.get("rule_matches", []):
                for parameter in match.get("parameters", []):
                    patterns += parameter["highlight"]
                    values.append(parameter["value"])
                    addresses.append(parameter["address"])
                    key_path = parameter["key_path"]
                    full_addresses.append((parameter["address"], key_path))
                    if isinstance(key_path, list) and len(key_path) != 0 and key_path[-1] in (0, "0"):
                        # on some frameworks, headers values can be arrays. In this case,
                        # key_path may contains a tailing 0. Remove it and add it as a possible use case.
                        key_path = key_path[:-1]
                        full_addresses.append((parameter["address"], key_path))

            if self.rule_id and self.rule_id != rule_id:
                logger.info(f"saw {rule_id}, expecting {self.rule_id}")

            elif self.rule_type and self.rule_type != rule_type:
                logger.info(f"saw rule type {rule_type}, expecting {self.rule_type}")

            elif self.pattern and self.pattern not in patterns:
                logger.info(f"saw {patterns}, expecting {self.pattern}")

            elif self.patterns and Counter(self.patterns) != Counter(patterns):
                logger.info(f"saw {patterns}, expecting {self.patterns}")

            elif self.value and self.value not in values:
                logger.info(f"saw {values}, expecting {self.value}")

            elif self.address and self.key_path is None and self.address not in addresses:
                logger.info(f"saw {addresses}, expecting {self.address}")

            elif self.address and self.key_path and (self.address, self.key_path) not in full_addresses:
                logger.info(f"saw {full_addresses}, expecting {(self.address, self.key_path)}")

            else:
                # validator should output the reason for the failure
                return not (self.span_validator and not self.span_validator(span, appsec_data))

        return None

    def validate_legacy(self, event: dict):
        event_version = event.get("event_version", "0.1.0")
        parameters = self._get_parameters(event)
        rule_match = event.get("rule_match", {})
        patterns = rule_match.get("highlight", rule_match.get("parameters", [{}])[0].get("highlight", []))
        rule_id = event.get("rule", {}).get("id")
        rule_type = event.get("rule", {}).get("tags", {}).get("type")
        addresses = [address for address, _ in parameters]

        # Some agent does not report rule type
        if not rule_type:
            rule_type = rule_id_to_type.get(rule_id)

        # be nice with very first AppSec data model, do not check key_path or rule_type
        key_path = self.key_path if event_version != "0.1.0" else None

        if self.rule_id and self.rule_id != rule_id:
            logger.info(f"saw rule id {rule_id}, expecting {self.rule_id}")

        elif self.rule_type and self.rule_type != rule_type:
            logger.info(f"saw rule type {rule_type}, expecting {self.rule_type}")

        elif self.pattern and self.pattern not in patterns:
            logger.info(f"saw {patterns}, expecting {self.pattern}")

        elif self.address and key_path is None and self.address not in addresses:
            logger.info(f"saw {addresses}, expecting {self.address}")

        elif self.address and key_path and (self.address, key_path) not in parameters:
            logger.info(f"saw {parameters}, expecting {(self.address, key_path)}")

        else:
            return True

        return False


class _ReportedHeader:
    def __init__(self, header_name: str):
        self.header_name = header_name.lower()

    def validate_legacy(self, event: dict):
        headers = [n.lower() for n in event["context"]["http"]["request"]["headers"]]
        assert self.header_name in headers, f"header {self.header_name} not reported"

        return True

    def validate(self, span: dict, appsec_data: dict):  # noqa: ARG002
        headers = [n.lower() for n in span["meta"] if n.startswith("http.request.headers.")]
        assert f"http.request.headers.{self.header_name}" in headers, f"header {self.header_name} not reported"

        return True
