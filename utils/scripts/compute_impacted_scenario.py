import json
from manifests.parser.core import load as load_manifests


def main():
    with open("logs/scenarios.json", "r", encoding="utf-8") as f:
        scenario_map = json.load(f)

    modified_nodeids = set()

    new_manifests = load_manifests("manifests/")
    old_manifests = load_manifests("original/manifests/")

    for nodeid in set(list(new_manifests.keys()) + list(old_manifests.keys())):
        if nodeid not in old_manifests or nodeid not in new_manifests or new_manifests[nodeid] != old_manifests[nodeid]:
            modified_nodeids.add(nodeid)

    impacted_scenarios = set()

    for nodeid in scenario_map:
        for modified_nodeid in modified_nodeids:
            if nodeid.startswith(modified_nodeid):
                impacted_scenarios.add(scenario_map[nodeid])
                break

    print(json.dumps(list(impacted_scenarios)))

if __name__ == "__main__":
    main()
