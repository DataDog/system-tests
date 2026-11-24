"""Print the images system-tests' own scenario definitions ask for, as JSON.

Run with the runner's Python, from a system-tests checkout (it imports `utils`):

    python scenario_images.py <SCENARIO>... --weblog <library>:<variant>...

prints {"<SCENARIO>": {"<variant>": ["<image>", ...]}}, the list being
`scenario.get_image_list(library, variant)`: the infrastructure images the scenario's containers
use and the images the weblog's Dockerfile is built FROM (base-image aliases resolved through
utils/build/docker/base-images.lock.json). Images system-tests builds itself (`system_tests/*`)
are left out, like utils/scripts/get-image-list.py does. Nothing is modified and Docker is not
contacted.
"""

import argparse
import json
import sys

sys.path.insert(0, ".")

from utils._context._scenarios import DockerScenario, get_all_scenarios  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenarios", nargs="+")
    parser.add_argument("--weblog", action="append", required=True, help="<library>:<variant>")
    args = parser.parse_args()

    scenarios = {s.name: s for s in get_all_scenarios()}
    result: dict[str, dict[str, list[str]]] = {}
    for name in args.scenarios:
        scenario = scenarios.get(name)
        if scenario is None:
            sys.exit(f"unknown scenario {name}")
        if not isinstance(scenario, DockerScenario):
            sys.exit(f"{name} is not a Docker scenario")
        result[name] = {}
        for weblog in args.weblog:
            library, variant = weblog.split(":", 1)
            images = scenario.get_image_list(library, variant)
            result[name][variant] = sorted({i for i in images if not i.startswith("system_tests/")})
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
