from collections import defaultdict
import requests


def to_camel_case(input):
    return "".join(ele.title() for ele in input.split("_"))


URL = (
    "https://raw.githubusercontent.com/DataDog/dd-trace-dotnet/master/tracer/src/Datadog.Trace/AppSec/Waf/rule-set.json"
)

data = requests.get(URL).json()

result = defaultdict(dict)
for event in data["events"]:
    name = event["id"]
    name = name.replace("-", "_")

    try:
        result[event["tags"]["type"]][name] = event
    except KeyError:
        print(event)

print("# Automatic generatiom from:")
print("#    python utils/scripts/extract_appsec_waf_rules.py > tests/appsec/waf/utils/rules.py")

for key, rules in result.items():
    print(f"\n\nclass {key}:")
    for name, event in rules.items():
        print(f"    {name} = \"{event['id']}\"  # {event['name']}")
