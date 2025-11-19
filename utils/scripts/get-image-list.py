import argparse
import json
import re
import yaml

from utils._context._scenarios import get_all_scenarios, DockerScenario
from utils._context.docker import get_docker_client


def main(scenarios: list[str], library: str, weblog: str) -> None:
    images = set("")

    existing_tags = []
    for image in get_docker_client().images.list():
        existing_tags.extend(image.tags)

    for scenario in get_all_scenarios():
        if scenario.name in scenarios and isinstance(scenario, DockerScenario):
            images.update(scenario.get_image_list(library, weblog))

    # remove images that will be built locally
    images = {image for image in images if not image.startswith("system_tests/")}

    # remove images that exists locally (they may not exists in the registry, ex: buddies)
    images = {image for image in images if image not in existing_tags}

    compose_data = {"services": {re.sub(r"[/:\.@]", "-", image): {"image": image} for image in sorted(images)}}

    print(yaml.dump(compose_data, default_flow_style=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="get-image-list", description="Get a docker-compose file with all images to pull"
    )
    parser.add_argument("scenarios", type=str, help="Scenarios to run. JSON array, or comma sparated string")
    parser.add_argument(
        "--library",
        "-l",
        type=str,
        default="",
        help="One of the supported Datadog library",
        choices=[
            "cpp",
            "cpp_httpd",
            "cpp_nginx",
            "dotnet",
            "python",
            "ruby",
            "golang",
            "java",
            "nodejs",
            "otel_collector",
            "php",
            "java_otel",
            "python_otel",
            "nodejs_otel",
            "python_lambda",
            "rust",
            "",
        ],
    )

    parser.add_argument("--weblog", "-w", type=str, help="End-to-end weblog", default="")

    args = parser.parse_args()

    if args.weblog and not args.library:
        parser.error("--weblog requires --library")
    if not args.weblog and args.library:
        parser.error("--library requires --weblog")

    main(
        json.loads(args.scenarios) if args.scenarios.startswith("[") else args.scenarios.split(","),
        library=args.library,
        weblog=args.weblog,
    )
