import json
import os
import os.path

_CUR_DIR = os.path.dirname(os.path.abspath(__file__))

MOCKED_RESPONSES = {}

for path in os.listdir(_CUR_DIR):
    if not path.startswith("rc_mocked_responses_"):
        continue
    if not path.endswith(".json"):
        continue
    scenario_name = path.replace("rc_mocked_responses_", "").replace(".json", "").upper()
    with open(os.path.join(_CUR_DIR, path), encoding="utf-8") as f:
        MOCKED_RESPONSES[scenario_name] = json.load(f)
