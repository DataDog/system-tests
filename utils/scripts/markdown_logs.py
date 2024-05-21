import os
import json
import collections


def table_row(*args):
    print(f"| {' | '.join(args)} |")


def main():
    result = {}
    all_outcomes = {"passed": "✅", "xpassed": "🍇", "skipped": "⏸️", "failed": "❌"}

    for x in os.listdir("."):
        if x.startswith("logs") and os.path.isfile(f"{x}/report.json"):
            result[x] = collections.defaultdict(int)
            data = json.load(open(f"{x}/report.json", "r"))
            for test in data["tests"]:
                outcome = "skipped" if test["metadata"]["details"] is not None else test["outcome"]
                result[x][outcome] += 1

    table_row("Scenario", *[f"{outcome} {icon}" for outcome, icon in all_outcomes.items()])
    table_row(*(["-"] * (len(all_outcomes) + 1)))

    for scenario, outcomes in result.items():
        if scenario == "logs":
            scenario = "Main scenario"
        else:
            # "ab_cd_ef" => "Ab Cd Ef"
            scenario = " ".join([s.capitalize() for s in scenario[5:].split("_")])

        table_row(scenario, *[str(outcomes.get(outcome, "")) for outcome in all_outcomes])


if __name__ == "__main__":
    main()
