import argparse
import json
import sys

from utils._context._scenarios import get_all_scenarios, Scenario, scenario_groups as all_scenarios_groups
from utils.scripts.ci_orchestrators.workflow_data import (
    get_aws_matrix,
    get_endtoend_definitions,
    get_docker_ssi_matrix,
    get_k8s_matrix,
    get_k8s_injector_dev_matrix,
)
from utils.scripts.ci_orchestrators.gitlab_exporter import print_gitlab_pipeline


def _clean_input_value(input_value: str) -> str:
    """Cleans the input value by removing spaces, newlines, and tabs."""
    return input_value.replace(" ", "").replace("\n", "").replace("\t", "")


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
        excluded_scenarios: str,
        weblogs: str,
        parametric_job_count: int,
        desired_execution_time: int,
        explicit_binaries_artifact: str,
        system_tests_dev_mode: bool,
        ci_environment: str | None,
    ):
        # this data struture is a dict where:
        #  the key is the workflow identifier
        #  the value is also a dict, where the key/value pair is the parameter name/value.
        self.data: dict[str, dict] = {"miscs": {}}
        self.language = library

        if ci_environment is not None:
            self.ci_environment = ci_environment
        elif system_tests_dev_mode:
            self.ci_environment = "dev"
            self.data["miscs"]["binaries_artifact"] = f"binaries_dev_{library}"
        elif len(explicit_binaries_artifact) != 0:
            self.ci_environment = "custom"
            self.data["miscs"]["binaries_artifact"] = explicit_binaries_artifact
        else:
            self.ci_environment = "prod"

        self.data["miscs"]["ci_environment"] = self.ci_environment

        # clean input parameters
        scenarios = _clean_input_value(scenarios)
        groups = _clean_input_value(groups)
        excluded_scenarios = _clean_input_value(excluded_scenarios)
        weblogs = _clean_input_value(weblogs)

        scenario_map = self._get_workflow_map(
            scenario_names=scenarios.split(","),
            scenario_group_names=groups.split(","),
            excluded_scenario_names=excluded_scenarios.split(","),
        )

        self.data |= get_endtoend_definitions(
            library,
            scenario_map,
            weblogs.split(",") if len(weblogs) > 0 else [],
            self.ci_environment,
            desired_execution_time,
            maximum_parallel_jobs=256,
        )

        self.data["parametric"] = {
            "job_count": parametric_job_count,
            "job_matrix": list(range(1, parametric_job_count + 1)),
            "enable": len(scenario_map["parametric"]) > 0
            and "otel" not in library
            and library not in ("cpp_nginx", "cpp_httpd", "python_lambda"),
        }

        self.data["externalprocessing"] = {"scenarios": scenario_map.get("externalprocessing", [])}
        self.data["streamprocessingoffload"] = {"scenarios": scenario_map.get("streamprocessingoffload", [])}

        self.data["libinjection_scenario_defs"] = get_k8s_matrix(
            "utils/scripts/ci_orchestrators/k8s_ssi.json",
            scenario_map.get("libinjection", []),
            library,
        )

        self.data["k8s_injector_dev_scenario_defs"] = get_k8s_injector_dev_matrix(
            "utils/scripts/ci_orchestrators/k8s_injector_dev.json",
            scenario_map.get("k8s_injector_dev", []),
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
                if isinstance(value, (dict, list)):
                    result.append(f"{workflow_name}_{parameter}={json.dumps(value)}")
                else:
                    result.append(f"{workflow_name}_{parameter}={value}")

        # github action is not able to handle aws_ssi, so nothing to do

        self._export("\n".join(result), output)

    def _export_gitlab(self) -> None:
        print_gitlab_pipeline(self.language, self.data, self.ci_environment)

    @staticmethod
    def _export(data: str, output: str) -> None:
        if output:
            with open(output, "w") as f:
                f.write(data)
        else:
            print(data)

    @staticmethod
    def _get_workflow_map(
        *, scenario_names: list[str], excluded_scenario_names: list[str], scenario_group_names: list[str]
    ) -> dict:
        """Returns a dict where:
        * the key is the workflow identifier
        * the value is a list of scenarios to run, associated to the workflow
        """

        result: dict[str, list[str]] = {}

        # clean inputs
        scenario_names = [scenario.strip() for scenario in scenario_names if scenario.strip()]
        scenario_group_names = [group.strip() for group in scenario_group_names if group.strip()]
        excluded_scenario_names = [scenario.strip() for scenario in excluded_scenario_names if scenario.strip()]

        # check that all scenarios provided by the user are valid
        existing_scenarios: dict[str, Scenario] = {scenario.name: scenario for scenario in get_all_scenarios()}
        for name in scenario_names:
            if name not in existing_scenarios:
                raise ValueError(f"Scenario {name} does not exists")

        # check that all groups provided by the user are valid
        for group in scenario_group_names:
            _ = all_scenarios_groups[group]

        for scenario in existing_scenarios.values():
            # TODO change the variable "github_workflow" to "ci_workflow" in the scenario object
            if not scenario.github_workflow:
                continue

            if scenario.github_workflow not in result:
                result[scenario.github_workflow] = []

            if scenario.name in excluded_scenario_names:
                continue

            if scenario.name in scenario_names:
                result[scenario.github_workflow].append(scenario.name)
            else:
                for group in scenario_group_names:
                    if all_scenarios_groups[group] in scenario.scenario_groups:
                        result[scenario.github_workflow].append(scenario.name)
                        break

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
            "python_lambda",
            "rust",
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
    parser.add_argument("--excluded-scenarios", type=str, help="Scenarios to excluded", default="")
    parser.add_argument("--weblogs", type=str, help="Subset of weblog to run", default="")

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
        "--explicit-binaries-artifact", type=str, help="If an artifact for binaries is explicitly provided", default=""
    )
    parser.add_argument(
        "--system-tests-dev-mode", type=str, help="true if running in system-tests CI, with  the dev mode", default=""
    )
    parser.add_argument("--ci-environment", type=str, help="Explicitly provide CI environment", default=None)

    args = parser.parse_args()

    if args.ci_environment is not None:
        if args.system_tests_dev_mode != "":
            print("--ci-environment is not compatible with --system-tests-dev-mode")
            sys.exit(1)

    CiData(
        library=args.library,
        scenarios=args.scenarios,
        groups=args.groups,
        excluded_scenarios=args.excluded_scenarios,
        weblogs=args.weblogs,
        parametric_job_count=args.parametric_job_count,
        desired_execution_time=args.desired_execution_time,
        explicit_binaries_artifact=args.explicit_binaries_artifact,
        system_tests_dev_mode=args.system_tests_dev_mode == "true",
        ci_environment=args.ci_environment,
    ).export(export_format=args.format, output=args.output)
