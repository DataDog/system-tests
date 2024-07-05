import os
import re
import sys
import yaml

from utils._context._scenarios import get_all_scenarios, _DockerScenario


if __name__ == "__main__":
    executed_scenarios = sys.argv[1]
    images = set("")

    for scenario in get_all_scenarios():
        if f'"{scenario.name}"' in executed_scenarios and isinstance(scenario, _DockerScenario):
            images.update(scenario.image_list)

    if os.environ.get("EXTRA_IMAGES"):
        images.update(os.environ["EXTRA_IMAGES"].split(","))

    # remove images that will be built locally
    images = [image for image in images if not image.startswith("system_tests/")]
    images.sort()

    compose_data = {"services": {re.sub(r"[/:\.]", "-", image): {"image": image} for image in images}}

    print(yaml.dump(compose_data, default_flow_style=False))
