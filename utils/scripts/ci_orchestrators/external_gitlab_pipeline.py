import yaml
import os

# List of allowed variables
ALLOWED_VARIABLES = [
    "SYSTEM_TESTS_SCENARIOS",
    "SYSTEM_TESTS_SCENARIOS_GROUPS",
    "K8S_LIB_INIT_IMG",
    "DD_INSTALLER_LIBRARY_VERSION",
    "K8S_INJECTOR_IMG",
    "DD_INSTALLER_INJECTOR_VERSION",
    "SYSTEM_TESTS_REF",
]

LANG_STAGES = ["java", "python", "nodejs", "dotnet", "ruby", "php"]


def main(language=None) -> None:
    """Main function to generate the gitlab system-tests pipeline
    Args:
        language (str): The language to filter the pipeline for.
        if it's None or not a language, the pipeline will be generated for all languages
    """
    # Filter environment variables
    new_variables = {var: os.getenv(var) for var in ALLOWED_VARIABLES if os.getenv(var) is not None}

    with open(".gitlab-ci.yml", "r") as file:
        data = yaml.safe_load(file)

    # Ensure 'variables' section exists and update with new values
    data.setdefault("variables", {}).update(new_variables)

    if language in LANG_STAGES:
        data = filter_yaml(data, language)

    handle_parallelism(data)

    # Print the modified YAML
    print(yaml.dump(data, default_flow_style=False, sort_keys=False))


def is_allowed_stage(stage, language) -> bool:
    """Check if a stage is allowed based on the language."""
    return stage in {language, "configure", "pipeline-status"}


def filter_yaml(yaml_data, language) -> dict:
    """Filter the pipeline to run only the jobs for the specified language"""

    # Find all jobs where stage == language
    allowed_jobs = {
        job_name: job_data
        for job_name, job_data in yaml_data.items()
        if isinstance(job_data, dict) and is_allowed_stage(job_data.get("stage"), language)
    }

    # Keep only relevant sections
    filtered_data = {key: yaml_data[key] for key in ["include", "variables", "stages"] if key in yaml_data}

    # Keep only the language stage
    if "stages" in filtered_data:
        filtered_data["stages"] = [stage for stage in yaml_data["stages"] if is_allowed_stage(stage, language)]

    # Add the filtered jobs only for the current language
    filtered_data.update(allowed_jobs)

    return filtered_data


def handle_parallelism(yaml_data) -> None:
    """Update jobs that have 'needs:' containing 'compute_pipeline' and another value, keeping only ['compute_pipeline']
    We will launch all the languges in parallel when we run system-tests in external repositories.
    (For the system-tests repository we launch the tests sequentially for each language.)
    NOTE: if we are running the tests for a release, we are going to run agains all vms, this can exhausted
          the resources (aws, gitlab). Let's add 5 minutes of delay for starting the next stage (for the next lang)
    """
    # Check if we are generating a release
    is_release = os.getenv("CI_COMMIT_TAG")
    # Add a delay job for each stage
    delayed = 3

    # Extract all defined stages and count how many stages belong to LANG_STAGES
    defined_stages = yaml_data.get("stages", [])
    lang_stage_count = sum(1 for stage in defined_stages if stage in LANG_STAGES)

    if lang_stage_count > 1 and is_release:
        for stage in yaml_data["stages"]:
            if stage in LANG_STAGES:
                job_name = f"delayed_{stage}_trigger"
                yaml_data[job_name] = {"extends": ".delayed_base_job", "stage": stage, "needs": ["compute_pipeline"]}
                yaml_data[job_name]["start_in"] = f"{delayed} minutes"
                delayed = delayed + 3

    for _job_name, job_data in yaml_data.items():  # noqa: PERF102
        if isinstance(job_data, dict) and "needs" in job_data:
            needs_list = job_data["needs"]
            # Check if 'compute_pipeline' is present and there is more than one value
            if isinstance(needs_list, list) and "compute_pipeline" in needs_list and len(needs_list) > 1:
                if lang_stage_count > 1 and is_release:
                    job_data["needs"] = [
                        "compute_pipeline",
                        f"delayed_{job_data['stage']}_trigger",
                    ]  # Delay the next stage
                else:
                    job_data["needs"] = ["compute_pipeline"]


if __name__ == "__main__":
    main(os.getenv("SYSTEM_TESTS_LIBRARY"))
