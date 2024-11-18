import json
import yaml
import argparse


from docker_ssi_definitions import ALL_WEBLOGS

def generate_gitlab_pipeline(languages):
    pipeline = {
        "stages": ["dummy"],
        # A dummy job is necessary for cases where all of the test jobs are manual
        # The child pipeline shows as failed until at least 1 job is run
        "dummy": {
            "image": "registry.ddbuild.io/docker:20.10.13-gbi-focal",
            "tags": ["arch:amd64"],
            "stage": "dummy",
            "needs": [],
            "script": [
                "echo 'DONE'"
            ]
        },
        ".base_ssi_job": {
            "image": "registry.ddbuild.io/ci/libdatadog-build/system-tests:48436362",
            "needs": [],
            "script": [
                "./build.sh -i runner",
                "source venv/bin/activate",
                "timeout 2700s ./run.sh DOCKER_SSI --ssi-weblog \"$weblog\" --ssi-library \"$TEST_LIBRARY\" --ssi-base-image \"$base_image\" --ssi-arch \"$arch\" --ssi-installable-runtime \"$installable_runtime\" --ssi-force-build"
            ],
            "rules": [
                {
                    "when": "manual",
                    "allow_failure": True
                }
            ],
            "artifacts": {
                "when": "always",
                "paths": ["logs_docker_ssi/"]
            }
        }
    };

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
                test.pop("unique_name", None)
                matrix.append(test)

        if matrix:
            pipeline[language] = {
                "extends": ".base_ssi_job",
                "tags": ["runner:$runner"],
                "stage": language,
                "variables": {
                    "TEST_LIBRARY": language,
                },
                "parallel": {
                    "matrix": matrix
                }
            }

    return pipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", required=True, type=str, choices=["json", "yaml"], help="json or yaml")
    parser.add_argument("--output-file", required=False, type=str)
    parser.add_argument("--language", required=False, type=str, help="Only generate config for single language")

    args = parser.parse_args()
    if (args.language):
        languages = [args.language]
    else:
        languages = ["java", "python", "nodejs", "dotnet", "ruby", "php"]

    pipeline = generate_gitlab_pipeline(languages)

    output = json.dumps(pipeline, sort_keys=False) if args.format == "json" else yaml.dump(pipeline, sort_keys=False, default_flow_style=False)
    print(output)
    if args.output_file is not None:
        with open(args.output_file, "w") as f:
            f.write(output)

if __name__ == "__main__":
    main()
