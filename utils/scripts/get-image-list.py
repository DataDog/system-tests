import re
import sys
import yaml

from utils._context._scenarios import get_all_scenarios, _DockerScenario


if __name__ == "__main__":
    executed_scenarios = sys.argv[1]
    exclude_buddies_images = sys.argv[2]

    images = set("")

    for scenario in get_all_scenarios():
        if f'"{scenario.name}"' in executed_scenarios and isinstance(scenario, _DockerScenario):
            images.update(scenario.image_list)

    # remove images that will be built locally
    images = [image for image in images if not image.startswith("system_tests/")]

    # if buddies will be rebuilt locally, no need to load them.
    # only usefull in system-tests CI
    if exclude_buddies_images != "false":
        images = [image for image in images if not re.match("^datadog/system-tests:.*buddy", image)]

    images.sort()

    compose_data = {"services": {re.sub(r"[/:\.]", "-", image): {"image": image} for image in images}}

    print(yaml.dump(compose_data, default_flow_style=False))
