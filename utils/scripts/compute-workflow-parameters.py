import argparse
import json

from utils._context._scenarios import get_all_scenarios, ScenarioGroup
from utils.scripts.ci_orchestrators.workflow_data import (
    get_aws_matrix,
    get_endtoend_definitions,
    get_docker_ssi_matrix,
    get_k8s_matrix,
)
from utils.scripts.ci_orchestrators.gitlab_exporter import print_gitlab_pipeline


class CiData:
    """CiData (Continuous Integration Data) class is used to store the data that is used to generate the CI workflow.
    It works in two separated steps:

        1. The first step, executed during __init__ build the full data structure about all possible workflows,
           based on arguments provided by the CI.
        2. The second step is to generate the workflow using the data stored in the object,
           and is acheived by calling export(format)
    """

    def __init__(
        self,
        *,
        library: str,
        scenarios: str,
        groups: str,
        parametric_job_count: int,
        desired_execution_time: int,
        explicit_artifact_name: str,
        system_tests_dev_mode: bool,
        gitlab_environment: str,
    ):
        # this data struture is a dict where:
        #  the key is the workflow identifier
        #  the value is also a dict, where the key/value pair is the parameter name/value.
        self.data: dict[str, dict] = {}
        self.language = library
        self.gitlab_environment = gitlab_environment
        self.ci_environment = (
            "dev" if system_tests_dev_mode else "prod" if len(explicit_artifact_name) == 0 else "custom"
        )
        scenario_map = self._get_workflow_map(scenarios.split(","), groups.split(","))

        self.data |= get_endtoend_definitions(
            library, scenario_map, self.ci_environment, desired_execution_time, maximum_parallel_jobs=256
        )

        self.data["miscs"] = {
            "artifact_name": f"binaries_dev_{library}" if system_tests_dev_mode else explicit_artifact_name,
            "ci_environment": self.ci_environment,
        }

        self.data["parametric"] = {
            "job_count": parametric_job_count,
            "job_matrix": list(range(1, parametric_job_count + 1)),
            "enable": len(scenario_map["parametric"]) > 0
            and "otel" not in library
            and library not in ("cpp_nginx", "cpp_httpd"),
        }

        self.data["libinjection_scenario_defs"] = get_k8s_matrix(
            "utils/scripts/ci_orchestrators/k8s_ssi.json",
            scenario_map.get("libinjection", []),
            library,
        )

        self.data["dockerssi_scenario_defs"] = get_docker_ssi_matrix(
            "utils/docker_ssi/docker_ssi_images.json",
            "utils/docker_ssi/docker_ssi_runtimes.json",
            "utils/scripts/ci_orchestrators/docker_ssi.json",
            scenario_map.get("dockerssi", []),
            library,
        )

        self.data["aws_ssi_scenario_defs"] = get_aws_matrix(
            "utils/virtual_machine/virtual_machines.json",
            "utils/scripts/ci_orchestrators/aws_ssi.json",
            scenario_map.get("aws_ssi", []),
            library,
        )

        # legacy part
        self.data["parametric"]["scenarios"] = ["PARAMETRIC"] if self.data["parametric"]["enable"] else []
        legacy_scenarios, legacy_weblogs = set(), set()

        for item in self.data["endtoend_defs"]["parallel_weblogs"]:
            legacy_weblogs.add(item)

        for job in self.data["endtoend_defs"]["parallel_jobs"]:
            for scenario in job["scenarios"]:
                legacy_scenarios.add(scenario)

        self.data["endtoend"] = {"weblogs": sorted(legacy_weblogs), "scenarios": sorted(legacy_scenarios)}

    def export(self, export_format: str, output: str) -> None:
        if export_format == "json":
            self._export(json.dumps(self.data), output)

        elif export_format == "github":
            self._export_github(output)

        elif export_format == "gitlab":
            if output != "":
                raise ValueError("Gitlab format does not support output file")
            self._export_gitlab()
        else:
            raise ValueError(f"Invalid format: {export_format}")

    def _export_github(self, output: str) -> None:
        result = []
        for workflow_name, workflow in self.data.items():
            for parameter, value in workflow.items():
                result.append(f"{workflow_name}_{parameter}={json.dumps(value)}")

        # github action is not able to handle aws_ssi, so nothing to do

        self._export("\n".join(result), output)

    def _export_gitlab(self) -> None:
        print_gitlab_pipeline(self.language, self.data, self.gitlab_environment)

    @staticmethod
    def _export(data: str, output: str) -> None:
        if output:
            with open(output, "w") as f:
                f.write(data)
        else:
            print(data)

    @staticmethod
    def _get_workflow_map(scenario_names: list[str], scenario_group_names: list[str]) -> dict:
        """Returns a dict where:
        * the key is the workflow identifier
        * the value is a list of scenarios to run, associated to the workflow
        """

        result: dict[str, list[str]] = {}

        scenarios_groups = [group.strip() for group in scenario_group_names if group.strip()]
        scenarios = {scenario.strip(): False for scenario in scenario_names if scenario.strip()}

        for group in scenarios_groups:
            try:
                ScenarioGroup(group)
            except ValueError as e:
                raise ValueError(f"Valid groups are: {[item.value for item in ScenarioGroup]}") from e

        for scenario in get_all_scenarios():
            # TODO change the variable "github_workflow" to "ci_workflow" in the scenario object
            if not scenario.github_workflow:
                scenarios[scenario.name] = True  # won't be executed, but it exists
                continue

            if scenario.github_workflow not in result:
                result[scenario.github_workflow] = []

            if scenario.name in scenarios:
                result[scenario.github_workflow].append(scenario.name)
                scenarios[scenario.name] = True

            for group in scenarios_groups:
                if ScenarioGroup(group) in scenario.scenario_groups:
                    result[scenario.github_workflow].append(scenario.name)
                    break

        for scenario_name, found in scenarios.items():
            if not found:
                raise ValueError(f"Scenario {scenario_name} does not exists")

        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="get-ci-parameters", description="Get scenarios and weblogs to run")
    parser.add_argument(
        "library",
        type=str,
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
            "php",
            "java_otel",
            "nodejs_otel",
            "python_otel",
        ],
    )

    parser.add_argument(
        "--format",
        "-f",
        type=str,
        help="Select the output format",
        choices=["github", "gitlab", "json"],
        default="github",
    )

    parser.add_argument("--scenarios", "-s", type=str, help="Scenarios to run", default="")
    parser.add_argument("--groups", "-g", type=str, help="Scenario groups to run", default="")

    # how long the workflow is expected to run
    parser.add_argument(
        "--desired-execution-time",
        "-t",
        type=int,
        help="Expected execution time of the workflow",
        default=-1,
    )
    # how long the workflow is expected to run
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="file (or folder) where to write the output",
        default="",
    )

    # workflow specific parameters
    parser.add_argument("--parametric-job-count", type=int, help="How may jobs must run parametric scenario", default=1)

    # Misc
    parser.add_argument(
        "--explicit-artifact-name", type=str, help="If an artifact name is explicitly provided", default=""
    )
    parser.add_argument(
        "--system-tests-dev-mode", type=str, help="If an artifact name is explicitly provided", default="false"
    )
    parser.add_argument(
        "--gitlab-environment", type=str, help="If an artifact name is explicitly provided", default="prod"
    )

    args = parser.parse_args()

    CiData(
        library=args.library,
        scenarios=args.scenarios,
        groups=args.groups,
        parametric_job_count=args.parametric_job_count,
        desired_execution_time=args.desired_execution_time,
        explicit_artifact_name=args.explicit_artifact_name,
        system_tests_dev_mode=args.system_tests_dev_mode == "true",
        gitlab_environment=args.gitlab_environment,
    ).export(export_format=args.format, output=args.output)
