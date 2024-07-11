import re
import sys
import yaml

from utils._context._scenarios import get_all_scenarios, DockerScenario


if __name__ == "__main__":
    library = sys.argv[1]
    weblog = sys.argv[2]
    executed_scenarios = sys.argv[3]

    images = set("")

    for scenario in get_all_scenarios():
        if f'"{scenario.name}"' in executed_scenarios and isinstance(scenario, DockerScenario):
            images.update(scenario.get_image_list(library, weblog))

    # remove images that will be built locally
    images = [image for image in images if not image.startswith("system_tests/")]

    # if buddies will be rebuilt locally, no need to load them.
    # only usefull in system-tests CI
    if exclude_buddies_images != "false":
        images = [image for image in images if not re.match("^datadog/system-tests:.*buddy", image)]

    images.sort()

    compose_data = {"services": {re.sub(r"[/:\.]", "-", image): {"image": image} for image in images}}

    print(yaml.dump(compose_data, default_flow_style=False))
