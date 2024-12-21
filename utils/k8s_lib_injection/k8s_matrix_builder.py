import json
import yaml
import argparse


def generate_gitlab_pipeline(languages):
    """Take k8s pipeline file and generate a pipeline for the specified languages"""
    result_pipeline = {}
    pipeline_file = f".gitlab/k8s_gitlab-ci.yml"
    pipeline_data = None
    with open(pipeline_file, encoding="utf-8") as f:
        pipeline_data = yaml.load(f, Loader=yaml.FullLoader)  # noqa: S506

    result_pipeline["stages"] = pipeline_data["stages"]
    result_pipeline[".k8s_lib_injection_base"] = pipeline_data[".k8s_lib_injection_base"]

    for language in languages:
        if pipeline_data["k8s_" + language] is not None:
            result_pipeline["k8s_" + language] = pipeline_data["k8s_" + language]
        else:
            raise Exception(f"Language {language} not found in the pipeline file")
    return result_pipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", required=True, type=str, choices=["json", "yaml"], help="json or yaml")
    parser.add_argument("--output-file", required=False, type=str)
    parser.add_argument("--language", required=False, type=str, help="Only generate config for single language")

    args = parser.parse_args()
    if args.language:
        languages = [args.language]
    else:
        languages = ["java", "python", "nodejs", "dotnet", "ruby"]

    pipeline = generate_gitlab_pipeline(languages)

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
