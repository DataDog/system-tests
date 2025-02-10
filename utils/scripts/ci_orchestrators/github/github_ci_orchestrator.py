import json


def print_github_output(result: dict[str, dict]) -> None:
    for workflow_name, workflow in result.items():
        for parameter, value in workflow.items():
            print(f"{workflow_name}_{parameter}={json.dumps(value)}")
