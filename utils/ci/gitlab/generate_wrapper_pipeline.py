#!/usr/bin/env python3
"""Generate a GitLab CI wrapper pipeline that includes main.yml with computed inputs."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a GitLab CI wrapper pipeline YAML")
    parser.add_argument("--libraries", required=True, help="Space-separated list of libraries")
    parser.add_argument("--scenarios", default="", help="Comma-separated list of scenarios")
    parser.add_argument("--scenarios-groups", default="", help="Comma-separated list of scenario groups")
    parser.add_argument(
        "--excluded-scenarios",
        default="",
        help="Comma-separated list of scenarios to exclude",
    )
    parser.add_argument("--ref", required=True, help="system-tests ref (branch, tag or SHA)")
    parser.add_argument(
        "--push-to-test-optimization",
        default="false",
        choices=["true", "false"],
        help="Push results to Datadog Test Optimization",
    )
    parser.add_argument("-o", "--output", required=True, help="Output file path")
    args = parser.parse_args()

    content = f"""include:
  - local: /utils/ci/gitlab/main.yml
    inputs:
      stage: build
      libraries: "{args.libraries}"
      scenarios: "{args.scenarios}"
      scenarios_groups: "{args.scenarios_groups}"
      excluded_scenarios: "{args.excluded_scenarios}"
      ref: "{args.ref}"
      push_to_test_optimization: {args.push_to_test_optimization}

stages:
  - build
"""

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    main()
