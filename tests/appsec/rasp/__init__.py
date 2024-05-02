def validate_rasp_attack(span, rule, parameters=None):
    assert "_dd.appsec.json" in span["meta"], "'_dd.appsec.json' not found in 'meta'"

    json = span["meta"]["_dd.appsec.json"]
    assert "triggers" in json, "'triggers' not found in '_dd.appsec.json'"

    triggers = json["triggers"]
    assert len(triggers) == 1, "multiple appsec events found, only one expected"

    trigger = triggers[0]
    obtained_rule_id = trigger["rule"]["id"]
    assert trigger["rule"]["id"] == rule, f"incorrect rule id, expected {rule}"

    if parameters is not None:
        rule_matches = trigger["rule_matches"]
        assert len(rule_matches) == 1, "multiple rule matches found, only one expected"

        rule_match_params = rule_matches[0]["parameters"]
        assert len(rule_match_params) == 1, "multiple parameters found, only one expected"

        obtained_parameters = rule_match_params[0]
        for name, fields in parameters.items():
            address = fields["address"]
            value = None
            if "value" in fields:
                value = fields["value"]

            key_path = None
            if "key_path" in fields:
                key_path = fields["key_path"]

            assert name in obtained_parameters, f"parameter '{name}' not in rule match"

            obtained_param = obtained_parameters[name]

            assert obtained_param["address"] == address, f"incorrect address for '{name}', expected '{address}'"

            if value is not None:
                assert obtained_param["value"] == value, f"incorrect value for '{name}', expected '{value}'"

            if key_path is not None:
                assert obtained_param["key_path"] == key_path, f"incorrect key_path for '{name}', expected '{key_path}'"
