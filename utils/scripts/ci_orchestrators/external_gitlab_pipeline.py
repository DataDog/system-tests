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
]


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

    if language in ["java", "python", "nodejs", "dotnet", "ruby", "php"]:
        data = filter_yaml(data, language)
    # Print the modified YAML
    print(yaml.dump(data, default_flow_style=False, sort_keys=False))


def filter_yaml(yaml_data, language) -> dict:
    """Filter the pipeline to run only the jobs for the specified language"""

    # Find all jobs where stage == language
    allowed_jobs = {
        job_name: job_data
        for job_name, job_data in yaml_data.items()
        if isinstance(job_data, dict) and (job_data.get("stage") == language or job_data.get("stage") == "configure")
    }

    # Keep only relevant sections
    filtered_data = {key: yaml_data[key] for key in ["include", "variables", "stages"] if key in yaml_data}

    # Keep only the language stage
    if "stages" in filtered_data:
        filtered_data["stages"] = [stage for stage in yaml_data["stages"] if stage == language or stage == "configure"]

    # Add the filtered jobs only for the current language
    filtered_data.update(allowed_jobs)

    return filtered_data


if __name__ == "__main__":
    main(os.getenv("SYSTEM_TESTS_LIBRARY"))
