import json
import yaml
import argparse


def generate_gitlab_pipeline(languages, env):
    """Take k8s pipeline file and generate a pipeline for the specified languages"""
    env = "prod" if env is None else env
    result_pipeline = {}
    pipeline_file = f".gitlab/k8s_gitlab-ci.yml"
    pipeline_data = None
    with open(pipeline_file, encoding="utf-8") as f:
        pipeline_data = yaml.load(f, Loader=yaml.FullLoader)  # noqa: S506

    result_pipeline["stages"] = pipeline_data["stages"]
    result_pipeline[".k8s_lib_injection_base"] = pipeline_data[".k8s_lib_injection_base"]
    result_pipeline["configure_env"] = pipeline_data["configure_env"]
    for language in languages:
        if pipeline_data["k8s_" + language] is not None:
            # Select the job based on the language
            result_pipeline["k8s_" + language] = pipeline_data["k8s_" + language]
            result_pipeline["k8s_" + language]["variables"].append({"ONBOARDING_FILTER_ENV": env})
            # Select the libray init image based on the env
            for matrix_item in result_pipeline["k8s_" + language]["parallel"]["matrix"]:
                seleted_matrix_item = None
                for matrix_image_item in matrix_item["K8S_LIB_INIT_IMG"]:
                    if (
                        env is None
                        or (env == "prod" and matrix_image_item.endswith("latest"))
                        or (env == "dev" and matrix_image_item.endswith("snapshot"))
                    ):
                        seleted_matrix_item = matrix_image_item
                        break
                if seleted_matrix_item is None:
                    raise Exception(f"Image not found for language {language} and env {env}")
                matrix_item["K8S_LIB_INIT_IMG"] = [seleted_matrix_item]
        else:
            raise Exception(f"Language {language} not found in the pipeline file")
    return result_pipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", required=True, type=str, choices=["json", "yaml"], help="json or yaml")
    parser.add_argument("--output-file", required=False, type=str)
    parser.add_argument("--language", required=False, type=str, help="Only generate config for single language")
    parser.add_argument("--env", required=False, type=str, help="Prod (latest and default) or dev (latest snapshot)")

    args = parser.parse_args()
    if args.language:
        languages = [args.language]
    else:
        languages = ["java", "python", "nodejs", "dotnet", "ruby"]

    pipeline = generate_gitlab_pipeline(languages, args.env)

    output = (
        json.dumps(pipeline, sort_keys=False)
        if args.format == "json"
        else yaml.dump(pipeline, sort_keys=False, default_flow_style=False)
    )
    if args.output_file is not None:
        with open(args.output_file, "w") as f:
            f.write(output)


if __name__ == "__main__":
    main()
