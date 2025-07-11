import collections
import json
import os
from pathlib import Path


def table_row(*args: str) -> None:
    print(f"| {' | '.join(args)} |")


def main() -> None:
    result: dict[str, dict[str, int]] = {}
    all_outcomes = {"passed": "✅", "xpassed": "🍇", "skipped": "⏸️", "failed": "❌"}

    for x in os.listdir("."):
        if x.startswith("logs") and Path(f"{x}/report.json").is_file():
            result[x] = collections.defaultdict(int)
            with open(f"{x}/report.json") as f:
                data = json.load(f)
            for test in data["tests"]:
                outcome = "skipped" if test["metadata"]["details"] is not None else test["outcome"]
                result[x][outcome] += 1

    table_row("Scenario", *[f"{outcome} {icon}" for outcome, icon in all_outcomes.items()])
    table_row(*(["-"] * (len(all_outcomes) + 1)))

    for folder_name, outcomes in result.items():
        if folder_name == "logs":
            scenario_name = "Main scenario"
        else:
            # "ab_cd_ef" => "Ab Cd Ef"
            scenario_name = " ".join([s.capitalize() for s in folder_name[5:].split("_")])

        table_row(scenario_name, *[str(outcomes.get(outcome, "")) for outcome in all_outcomes])


if __name__ == "__main__":
    main()
