#!/usr/bin/env python3
"""Helper script to inspect K8s scenario properties for the wizard."""

import argparse
import sys
from pathlib import Path

# Add system-tests root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

try:
    from utils._context._scenarios import get_all_scenarios
except ImportError as e:
    print(f"ERROR: Failed to import scenarios module: {e}", file=sys.stderr)
    print("Make sure the script is run from the system-tests root directory", file=sys.stderr)
    sys.exit(1)


def get_scenario_properties(scenario_name: str) -> dict[str, bool]:
    """Get scenario properties by name.

    Args:
        scenario_name: Scenario name (e.g., K8S_LIB_INJECTION, K8S_LIB_INJECTION_NO_AC)

    Returns:
        Dictionary with scenario properties:
        - with_cluster_agent: bool
        - with_datadog_operator: bool

    Raises:
        SystemExit: If scenario not found

    """
    all_scenarios = get_all_scenarios()

    # Find the scenario
    scenario = next((s for s in all_scenarios if s.name == scenario_name), None)

    if scenario is None:
        print(f"ERROR: Scenario '{scenario_name}' not found", file=sys.stderr)
        sys.exit(1)

    # Extract properties with safe defaults
    return {
        "with_cluster_agent": getattr(scenario, "with_cluster_agent", False),
        "with_datadog_operator": getattr(scenario, "with_datadog_operator", False),
    }


def main() -> None:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(description="Inspect K8s scenario properties")
    parser.add_argument("scenario", help="Scenario name (e.g., K8S_LIB_INJECTION)")
    parser.add_argument(
        "--property",
        choices=["with_cluster_agent", "with_datadog_operator"],
        help="Get specific property (returns true/false)",
    )

    args = parser.parse_args()

    try:
        properties = get_scenario_properties(args.scenario)

        if args.property:
            # Return specific property as true/false for shell
            print("true" if properties[args.property] else "false")
        else:
            # Return all properties as key=value pairs for shell eval
            for key, value in properties.items():
                print(f"{key}={'true' if value else 'false'}")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
