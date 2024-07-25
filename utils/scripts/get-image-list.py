import re
import sys
import yaml

from utils._context._scenarios import get_all_scenarios, DockerScenario
from utils._context.containers import _get_client


if __name__ == "__main__":
    library = sys.argv[1]
    weblog = sys.argv[2]
    executed_scenarios = sys.argv[3]

    images = set("")

    existing_tags = []
    for image in _get_client().images.list():
        existing_tags.extend(image.tags)

    for scenario in get_all_scenarios():
        if f'"{scenario.name}"' in executed_scenarios and isinstance(scenario, DockerScenario):
            images.update(scenario.get_image_list(library, weblog))

    # remove images that will be built locally
    images = [image for image in images if not image.startswith("system_tests/")]

    # remove images that exists locally (they may not exists in the registry, ex: buddies)
    images = [image for image in images if image not in existing_tags]

    images.sort()

    compose_data = {"services": {re.sub(r"[/:\.]", "-", image): {"image": image} for image in images}}

    print(yaml.dump(compose_data, default_flow_style=False))
