# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import sys
from collections import defaultdict
import requests


def to_camel_case(input):
    return "".join(ele.title() for ele in input.split("_"))


sources = {
    "dotnet": "https://raw.githubusercontent.com/DataDog/dd-trace-dotnet/master/tracer/src/Datadog.Trace/AppSec/Waf/rule-set.json",
    "nodejs": "https://raw.githubusercontent.com/DataDog/dd-trace-js/vdeturckheim/iaw-bindings/packages/dd-trace/src/appsec/recommended.json",
    "ruby": "https://raw.githubusercontent.com/DataDog/dd-trace-rb/appsec/lib/datadog/security/assets/waf_rules.json",
}

URL = sources[sys.argv[1]]

data = requests.get(URL).json()

version = data["version"]

rules_key = {"1.0": "events", "2.1": "rules"}[version]

result = defaultdict(dict)
for event in data[rules_key]:
    name = event["id"]
    name = name.replace("-", "_")

    try:
        result[event["tags"]["type"]][name] = event
    except KeyError:
        print(event)

with open("tests/appsec/waf/utils/rules.py", "w") as f:
    f.write(
        f"""# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
    # This product includes software developed at Datadog (https://www.datadoghq.com/).
    # Copyright 2021 Datadog, Inc.

    # Automatic generatiom from:
    #    python utils/scripts/extract_appsec_waf_rules.py {sys.argv[1]}
"""
    )

    for key, rules in result.items():
        f.write(f"\n\nclass {key}:\n")
        for name, event in rules.items():
            f.write(f"    {name} = \"{event['id']}\"  # {event['name']}\n")
