from ddtrace import appsec
import json


path = appsec.__path__[0] + "/rules.json"
data = json.load(open(path))

if "metadata" not in data:
    print("1.2.5")
else:
    print(data["metadata"]["rules_version"])
