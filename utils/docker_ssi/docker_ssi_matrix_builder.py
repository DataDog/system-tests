import json
import yaml
import argparse


from docker_ssi_definitions import ALL_WEBLOGS

def generate_gitlab_pipeline():
    pipeline = {
        "stages": [],
        ".base_ssi_job": {
            "image": "registry.ddbuild.io/ci/libdatadog-build/system-tests:48436362",
            "dependencies": [],
            "script": [
                "./build.sh -i runner",
                "source venv/bin/activate",
                "timeout 2700s ./run.sh DOCKER_SSI --ssi-weblog \"$weblog\" --ssi-library \"$TEST_LIBRARY\" --ssi-base-image \"$base_image\" --ssi-arch \"$arch\" --ssi-installable-runtime \"$installable_runtime\""
            ],
            "rules": [
                { "when": "manual" }
            ],
            "artifacts": {
                "when": "always",
                "paths": ["logs_docker_ssi/"]
            }
        }
    };

    languages = ["java","python","nodejs","dotnet","ruby","php"]

    for language in languages:
        pipeline["stages"].append(language)
        matrix = []

        filtered = [weblog for weblog in ALL_WEBLOGS if weblog.library == language]
        for weblog in filtered:
            weblog_matrix = weblog.get_matrix()
            if not weblog_matrix:
                continue
            for test in weblog_matrix:
                if test["arch"] == "linux/amd64":
                    test["runner"] = "docker"
                else:
                    test["runner"] = "docker-arm"
                matrix.append(test)

        if matrix:
            pipeline[language] = {
                "extends": ".base_ssi_job",
                "tags": ["runner:$runner"],
                "parallel": {
                    "matrix": matrix
                }
            }

    return pipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", required=True, type=str, choices=["json", "yaml"], help="json or yaml")
    parser.add_argument("--output-file", required=False, type=str)

    args = parser.parse_args()
    pipeline = generate_gitlab_pipeline()

    output = json.dumps(pipeline, sort_keys=False) if args.format == "json" else yaml.dump(pipeline, sort_keys=False, default_flow_style=False)
    print(output)
    if args.output_file is not None:
        with open(args.output_file, "w") as f:
            f.write(output)

if __name__ == "__main__":
    main()
