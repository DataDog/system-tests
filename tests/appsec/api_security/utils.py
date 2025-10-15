from utils import remote_config


class BaseAppsecApiSecurityRcTest:
    states = None

    def setup_scenario(self) -> None:
        if BaseAppsecApiSecurityRcTest.states is None:
            rc_state = remote_config.rc_state
            rc_state.set_config(
                "datadog/2/ASM/ASM-base/config",
                {
                    "processor_overrides": [
                        {
                            "target": [{"id": "extract-content"}],
                            "scanners": {
                                "include": [{"id": "test-scanner-001"}, {"id": "test-scanner-custom-001"}],
                                "exclude": [],
                            },
                        }
                    ],
                    "scanners": [
                        {
                            "id": "test-scanner-custom-001",
                            "name": "Custom scanner",
                            "key": {
                                "operator": "match_regex",
                                "parameters": {
                                    "regex": "\\btestcard\\b",
                                    "options": {"case_sensitive": False, "min_length": 2},
                                },
                            },
                            "value": {
                                "operator": "match_regex",
                                "parameters": {
                                    "regex": "\\b1234567890\\b",
                                    "options": {"case_sensitive": False, "min_length": 5},
                                },
                            },
                            "tags": {"type": "card", "category": "testcategory"},
                        }
                    ],
                },
            )
            rc_state.set_config(
                "datadog/2/ASM_DD/ASM_DD-base/config",
                {
                    "version": "2.2",
                    "metadata": {"rules_version": "1.10.0"},
                    "rules": [
                        {
                            "id": "test-001",
                            "name": "Test 001 rule",
                            "tags": {"type": "commercial_scanner", "category": "attack_attemp"},
                            "conditions": [
                                {
                                    "parameters": {
                                        "inputs": [
                                            {"address": "server.request.query"},
                                            {"address": "server.request.uri.raw"},
                                            {"address": "server.request.body"},
                                        ],
                                        "regex": "testattack",
                                        "options": {"case_sensitive": False},
                                    },
                                    "operator": "match_regex",
                                }
                            ],
                        }
                    ],
                    "processors": [
                        {
                            "id": "extract-content",
                            "generator": "extract_schema",
                            "conditions": [
                                {
                                    "operator": "equals",
                                    "parameters": {
                                        "inputs": [
                                            {"address": "waf.context.processor", "key_path": ["extract-schema"]}
                                        ],
                                        "type": "boolean",
                                        "value": True,
                                    },
                                }
                            ],
                            "parameters": {
                                "mappings": [
                                    {
                                        "inputs": [{"address": "server.request.query"}],
                                        "output": "_dd.appsec.s.req.querytest",
                                    },
                                    {
                                        "inputs": [{"address": "server.request.body"}],
                                        "output": "_dd.appsec.s.req.bodytest",
                                    },
                                ],
                                "scanners": [{"tags": {"category": "pii"}}],
                            },
                            "evaluate": True,
                            "output": True,
                        }
                    ],
                    "scanners": [
                        {
                            "id": "test-scanner-001",
                            "name": "Standard E-mail Address",
                            "key": {
                                "operator": "match_regex",
                                "parameters": {
                                    "regex": "\\b(?:(?:e[-\\s]?)?mail|address|sender|\\bto\\b|from|recipient)\\b",
                                    "options": {"case_sensitive": False, "min_length": 2},
                                },
                            },
                            "value": {
                                "operator": "match_regex",
                                "parameters": {
                                    "regex": "\\b[\\w!#$%&'*+/=?`{|}~^-]+(?:\\.[\\w!#$%&'*+/=?`{|}~^-]+)*"
                                    "(%40|@)(?:[a-zA-Z0-9-]+\\.)+[a-zA-Z]{2,6}\\b",
                                    "options": {"case_sensitive": False, "min_length": 5},
                                },
                            },
                            "tags": {"type": "email", "category": "pii"},
                        }
                    ],
                },
            )
            rc_state.set_config(
                "datadog/2/ASM_FEATURES/ASM_FEATURES-base/config",
                {"asm": {"enabled": True}},
            )

            BaseAppsecApiSecurityRcTest.states = rc_state.apply()
